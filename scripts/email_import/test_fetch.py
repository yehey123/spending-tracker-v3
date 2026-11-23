import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "sandbox"))
import fetch  # noqa: E402
from fetch import Rejected, attachment_parts, dkim_ok, from_address, password_for  # noqa: E402
import flatten as worker  # noqa: E402  (sandbox/flatten.py, tested directly with host PyMuPDF)

GMAIL_AR = ("mx.google.com; dkim=pass header.i=@mybank.com header.s=s1 header.b=abc; "
            "spf=pass smtp.mailfrom=mybank.com; dmarc=pass header.from=mybank.com")


def test_dkim_pass_for_own_domain():
    assert dkim_ok(GMAIL_AR, "estatement@mybank.com")
    assert dkim_ok(GMAIL_AR, "estatement@mail.mybank.com")  # subdomain of signer


def test_dkim_rejects_spoof_and_fail():
    assert not dkim_ok(GMAIL_AR.replace("mybank.com", "evil.com"), "estatement@mybank.com")
    assert not dkim_ok(GMAIL_AR.replace("dkim=pass", "dkim=fail"), "estatement@mybank.com")
    assert not dkim_ok("dkim=pass header.i=@notmybank.com", "x@mybank.com")  # suffix trick
    assert not dkim_ok("", "x@mybank.com")


def test_from_address():
    assert from_address('"My Bank" <EStatement@MyBank.com>') == "estatement@mybank.com"


def test_password_template(monkeypatch):
    monkeypatch.setenv("BD", "01021990")
    monkeypatch.setenv("L4", "1234")
    assert password_for({"password": "{BD}{L4}"}) == "010219901234"
    assert password_for({}) is None
    monkeypatch.delenv("L4")
    with pytest.raises(Rejected):
        password_for({"password": "{BD}{L4}"})


def test_attachment_filter():
    payload = {"parts": [
        {"mimeType": "application/pdf", "filename": "s.pdf", "body": {}},
        {"mimeType": "image/jpeg", "filename": "r.jpg", "body": {}},
        {"mimeType": "application/x-msdownload", "filename": "s.pdf.exe", "body": {}},
        {"mimeType": "image/svg+xml", "filename": "x.svg", "body": {}},
        {"mimeType": "text/html", "body": {"data": "aA"}},
    ]}
    assert [p["filename"] for p in attachment_parts(payload)] == ["s.pdf", "r.jpg"]


def _evil_locked_pdf():
    fitz = pytest.importorskip("pymupdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "TOTAL 123.45")
    doc.embfile_add("payload.exe", b"MZ evil")
    return fitz, doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="o")


def _assert_clean(fitz, pdf):
    out = fitz.open(stream=pdf)
    assert out.page_count == 1
    assert not out.needs_pass
    assert out.embfile_count() == 0
    assert out[0].get_text().strip() == ""  # image-only: no text layer survives
    assert out[0].get_images()




def test_worker_unlocks_and_strips_active_content():
    fitz, src = _evil_locked_pdf()
    with pytest.raises(worker.Rejected):
        worker.flatten(src, "wrong")
    _assert_clean(fitz, worker.flatten(src, "pw"))


def test_worker_rejects_non_pdf():
    with pytest.raises(worker.Rejected):
        worker.flatten(b"MZ\x90\x00 executable", None)


def _docker_up():
    import subprocess
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


docker = pytest.mark.skipif(not _docker_up(), reason="Docker daemon not running")


@docker
def test_sandbox_end_to_end():
    fitz, src = _evil_locked_pdf()
    image = fetch.sandbox_image()
    _assert_clean(fitz, fetch.flatten(image, src, "pw"))
    with pytest.raises(Rejected, match="exit 3"):
        fetch.flatten(image, src, "wrong")
    with pytest.raises(Rejected, match="exit 3"):
        fetch.flatten(image, b"MZ\x90\x00 executable", None)


@docker
def test_sandbox_has_no_network_and_readonly_root():
    import subprocess
    probe = ("import socket,sys\n"
             "try: socket.create_connection(('1.1.1.1',53),3); sys.exit('NET')\n"
             "except OSError: pass\n"
             "try: open('/app/x','w'); sys.exit('WRITE')\n"
             "except OSError: pass\n")
    r = subprocess.run(["docker", "run", *fetch.SANDBOX_FLAGS, "--entrypoint", "python",
                        fetch.sandbox_image(), "-c", probe], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
