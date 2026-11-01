import { createSignal, For } from 'solid-js';

interface LogViewerProps {
  logs: () => any[];
  loading?: boolean;
  maxHeight?: string;
}

export function LogViewer(props: LogViewerProps) {
  const maxHeight = props.maxHeight || '500px';

  return (
    <div class="border border-gray-300 rounded bg-gray-50 p-4" style={{ 'max-height': maxHeight, 'overflow-y': 'auto' }}>
      <div class="font-mono text-sm">
        <For each={props.logs()}>
          {(log) => (
            <div class="py-1 border-b border-gray-200 last:border-b-0">
              <span class="text-gray-500">{log.timestamp}</span>
              {' '}
              <span class={`font-bold ${log.level === 'ERROR' ? 'text-red-600' : 'text-green-600'}`}>
                [{log.level}]
              </span>
              {' '}
              <span class="text-gray-700">{log.message}</span>
            </div>
          )}
        </For>
        {props.logs().length === 0 && (
          <div class="text-gray-400">No logs yet...</div>
        )}
      </div>
    </div>
  );
}
