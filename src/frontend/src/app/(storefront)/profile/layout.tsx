import { AccountShell } from '../../../features/profile/AccountShell';

// Khung chung của /profile và /profile/booking_history (FR-USR-04, FR-BKG-14).
export default function ProfileLayout({ children }: { children: React.ReactNode }) {
  return <AccountShell>{children}</AccountShell>;
}
