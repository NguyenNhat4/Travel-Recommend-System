import type { LucideIcon } from 'lucide-react';
import { Building2, Flag, Package, Plane, Ticket } from 'lucide-react';
import type { NavIcon as NavIconName } from './navConfig';

const ICONS: Record<NavIconName, LucideIcon> = {
  plane: Plane,
  hotel: Building2,
  ticket: Ticket,
  flag: Flag,
  package: Package,
};

export function NavIcon({ name, className = 'w-4 h-4' }: { name: NavIconName; className?: string }) {
  const Icon = ICONS[name];
  return <Icon className={className} aria-hidden="true" />;
}
