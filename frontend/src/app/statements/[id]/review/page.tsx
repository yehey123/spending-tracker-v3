import StatementReviewPageClient from './StatementReviewPageClient';

export async function generateStaticParams() {
  return [{ id: 'placeholder' }];
}

export default function StatementReviewPage() {
  return <StatementReviewPageClient />;
}
