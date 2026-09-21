import { ConfirmationView } from '../../../../components/confirmation/ConfirmationView';

export default async function BookingPage({
  params,
}: {
  params: Promise<{ referenceCode: string }>;
}) {
  const { referenceCode } = await params;
  return <ConfirmationView referenceCode={referenceCode} />;
}
