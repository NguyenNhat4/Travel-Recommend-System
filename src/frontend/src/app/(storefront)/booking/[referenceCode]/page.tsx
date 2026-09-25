import { ConfirmationView } from '../../../../components/confirmation/ConfirmationView';

export default async function BookingPage({
  params,
  searchParams,
}: {
  params: Promise<{ referenceCode: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { referenceCode } = await params;
  const { payment } = await searchParams;
  return <ConfirmationView referenceCode={referenceCode} paymentReturn={typeof payment === 'string' ? payment : undefined} />;
}
