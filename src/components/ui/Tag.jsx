import { cn } from '../../utils/classnames';

const colors = {
  indigo: 'tag-indigo', purple: 'tag-purple', pink: 'tag-pink',
  green: 'tag-green', yellow: 'tag-yellow', red: 'tag-red',
  blue: 'tag-blue', gray: 'tag-gray',
};

export function Tag({ children, color = 'indigo', className }) {
  return (
    <span className={cn('tag', colors[color], className)}>
      {children}
    </span>
  );
}
