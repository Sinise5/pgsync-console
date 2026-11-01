import { createSignal, Show } from 'solid-js';

interface ButtonProps {
  type?: 'button' | 'submit' | 'reset';
  variant?: 'default' | 'primary' | 'danger' | 'secondary';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  children: any;
}

export function Button(props: ButtonProps) {
  const variants = {
    default: 'bg-gray-200 text-gray-800 hover:bg-gray-300',
    primary: 'bg-blue-600 text-white hover:bg-blue-700',
    danger: 'bg-red-600 text-white hover:bg-red-700',
    secondary: 'bg-gray-300 text-gray-800 hover:bg-gray-400',
  };

  const sizes = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  const variant = props.variant || 'default';
  const size = props.size || 'md';

  return (
    <button
      type={props.type || 'button'}
      class={`rounded font-medium transition ${variants[variant]} ${sizes[size]} disabled:opacity-50 disabled:cursor-not-allowed`}
      onClick={props.onClick}
      disabled={props.disabled || props.loading}
    >
      <Show when={props.loading} fallback={props.children}>
        <span class="spinner mr-2" />
        Loading...
      </Show>
    </button>
  );
}

interface CardProps {
  children: any;
  title?: string;
  subtitle?: string;
}

export function Card(props: CardProps) {
  return (
    <div class="border border-gray-200 rounded-lg bg-white shadow-sm p-6">
      <Show when={props.title}>
        <h3 class="text-lg font-semibold mb-2">{props.title}</h3>
        <Show when={props.subtitle}>
          <p class="text-sm text-gray-600 mb-4">{props.subtitle}</p>
        </Show>
      </Show>
      {props.children}
    </div>
  );
}

interface BadgeProps {
  variant?: 'default' | 'secondary' | 'success' | 'error' | 'warning' | 'info';
  children: any;
}

export function Badge(props: BadgeProps) {
  const variants = {
    default: 'bg-gray-100 text-gray-800',
    secondary: 'bg-gray-200 text-gray-700',
    success: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
    warning: 'bg-yellow-100 text-yellow-800',
    info: 'bg-blue-100 text-blue-800',
  };

  const variant = props.variant || 'info';

  return (
    <span class={`inline-block px-3 py-1 rounded-full text-xs font-medium ${variants[variant]}`}>
      {props.children}
    </span>
  );
}
