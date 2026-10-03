import { Badge } from './ui/Badge';

const STATUS_MAP = {
  pending: { type: 'warning', label: 'Pending' },
  processing: { type: 'info', label: 'Processing' },
  completed: { type: 'success', label: 'Done' },
  failed: { type: 'error', label: 'Failed' },
  cancelled: { type: 'default', label: 'Cancelled' },
};

export function JobStatusBadge({ status, className }) {
  const { type, label } = STATUS_MAP[status] || { type: 'default', label: status };
  return <Badge type={type} className={className}>{label}</Badge>;
}
