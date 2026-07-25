import PortfolioPageClient from './PortfolioPageClient';

export async function generateStaticParams() {
  return [{ accountId: 'placeholder' }];
}

export default function PortfolioPage() {
  return <PortfolioPageClient />;
}
