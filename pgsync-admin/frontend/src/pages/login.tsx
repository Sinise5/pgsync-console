import { createSignal, onMount, Show } from 'solid-js';
import { apiClient } from '@/lib/api-client';

export function LoginPage(props: { onLogin: () => void }) {
  const [demoCredentials, setDemoCredentials] = createSignal<{ username: string; password: string } | null>(null);
  const [username, setUsername] = createSignal('');
  const [password, setPassword] = createSignal('');
  const [showPassword, setShowPassword] = createSignal(false);
  const [error, setError] = createSignal('');
  const [loading, setLoading] = createSignal(false);

  onMount(async () => {
    try {
      const response = await apiClient.getDemoCredentials();
      setDemoCredentials(response.data);
    } catch {
      setDemoCredentials(null);
    }
  });

  const submit = async (event: SubmitEvent) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const response = await apiClient.login(username(), password());
      localStorage.setItem('pgsync_admin_token', response.data.token);
      props.onLogin();
    } catch {
      setError('Login gagal. Periksa username dan password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main class="min-h-screen flex items-center justify-center px-4 py-10">
      <section class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <p class="text-sm font-semibold uppercase tracking-wide text-teal-700">PGSync Admin</p>
        <h1 class="mt-2 text-2xl font-bold text-gray-900">Masuk ke Admin</h1>
        <p class="mt-1 text-sm text-gray-600">Gunakan akun admin yang dikonfigurasi pada server.</p>

        <Show when={demoCredentials()}>
          {(credentials) => (
            <aside class="mt-5 rounded border border-teal-200 bg-teal-50 p-4 text-sm text-teal-950" aria-label="Akun demo lokal">
              <p class="font-semibold">Akun demo lokal</p>
              <p class="mt-2">Username: <code>{credentials().username}</code></p>
              <p>Password: <code class="break-all">{credentials().password}</code></p>
              <button
                class="mt-3 font-semibold text-teal-800 underline underline-offset-2 hover:text-teal-950"
                type="button"
                onClick={() => {
                  setUsername(credentials().username);
                  setPassword(credentials().password);
                }}
              >
                Isi form login
              </button>
            </aside>
          )}
        </Show>

        <Show when={error()}>
          <p class="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{error()}</p>
        </Show>

        <form class="mt-6 space-y-4" onSubmit={submit}>
          <label class="block text-sm font-medium text-gray-700">
            Username
            <input
              class="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-gray-900"
              name="username"
              autocomplete="username"
              required
              value={username()}
              onInput={(event) => setUsername(event.currentTarget.value)}
            />
          </label>
          <label class="block text-sm font-medium text-gray-700">
            Password
            <span class="mt-1 flex rounded border border-gray-300 bg-white focus-within:ring-2 focus-within:ring-teal-700">
              <input
                id="login-password"
                class="min-w-0 flex-1 rounded-l px-3 py-2 text-gray-900 focus:outline-none"
                name="password"
                type={showPassword() ? 'text' : 'password'}
                autocomplete="current-password"
                required
                value={password()}
                onInput={(event) => setPassword(event.currentTarget.value)}
              />
              <button
                class="rounded-r px-3 text-sm font-medium text-teal-800 hover:bg-teal-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-teal-700"
                type="button"
                aria-controls="login-password"
                aria-pressed={showPassword()}
                onClick={() => setShowPassword((visible) => !visible)}
              >
                {showPassword() ? 'Sembunyikan' : 'Tampilkan'}
              </button>
            </span>
          </label>
          <button
            class="w-full rounded bg-teal-700 px-4 py-2.5 font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={loading()}
          >
            {loading() ? 'Memeriksa…' : 'Masuk'}
          </button>
        </form>
      </section>
    </main>
  );
}
