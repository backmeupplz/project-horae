(() => {
  const form = document.getElementById('waitlist-form');
  if (!form) return;
  const fields = document.getElementById('waitlist-fields');
  const email = document.getElementById('waitlist-email');
  const website = document.getElementById('waitlist-website');
  const button = document.getElementById('waitlist-submit');
  const status = document.getElementById('waitlist-status');
  let busy = false;
  let retryAt = 0;
  fields.disabled = false;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (busy || !form.reportValidity()) return;
    if (Date.now() < retryAt) {
      status.textContent = 'Please wait ' + Math.ceil((retryAt - Date.now()) / 1000) + ' seconds, then try again.';
      return;
    }
    busy = true;
    button.disabled = true;
    email.readOnly = true;
    form.setAttribute('aria-busy', 'true');
    button.textContent = 'Joining…';
    status.textContent = 'Saving your email…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'omit',
        referrerPolicy: 'no-referrer',
        signal: controller.signal,
        body: JSON.stringify({ email: email.value.trim(), website: website.value }),
      });
      if (response.status === 429 || response.status === 503) {
        const raw = response.headers.get('Retry-After');
        const seconds = raw && /^\d+$/.test(raw) ? Number(raw) : 30;
        retryAt = Date.now() + Math.min(Math.max(seconds, 1), 3600) * 1000;
        status.textContent = 'Please wait ' + Math.ceil((retryAt - Date.now()) / 1000) + ' seconds, then try again. Your email is still in the form.';
        button.textContent = 'Try again';
      } else if (response.status === 400) {
        status.textContent = 'Please check your email address and try again.';
        button.textContent = 'Try again';
      } else {
        if (!response.ok || (await response.json()).ok !== true) throw new Error('Signup unavailable');
        status.textContent = "You're on the waitlist. Thank you!";
        form.reset();
        button.textContent = 'Join the waitlist';
      }
    } catch {
      status.textContent = "We couldn't confirm your signup. Please try again; retrying won't add you twice.";
      button.textContent = 'Try again';
    } finally {
      clearTimeout(timeout);
      busy = false;
      button.disabled = false;
      email.readOnly = false;
      form.setAttribute('aria-busy', 'false');
    }
  });
})();
