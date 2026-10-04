const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = readFileSync(path.join(__dirname, '../waitlist.js'), 'utf8');
const html = readFileSync(path.join(__dirname, '../index.html'), 'utf8');

function setup(fetch) {
  const elements = Object.fromEntries(['form', 'fields', 'email', 'website', 'submit', 'status'].map(name => ['waitlist-' + name, { value: '', textContent: '', disabled: true, attributes: {} }]));
  const form = elements['waitlist-form'];
  const email = elements['waitlist-email'];
  form.action = 'https://horae-waitlist.borodutch.com/api/waitlist';
  form.reportValidity = () => true;
  form.setAttribute = (name, value) => { form.attributes[name] = value; };
  form.addEventListener = (_, callback) => { form.submit = () => callback({ preventDefault() {} }); };
  form.reset = () => { email.value = ''; };
  email.value = 'a.b+tag@example.com';
  let timer;
  let now = 100000;
  vm.runInNewContext(script, {
    document: { getElementById: id => elements[id] }, fetch, AbortController,
    setTimeout: callback => { timer = callback; return 1; }, clearTimeout: () => { timer = null; },
    Date: { now: () => now },
  });
  return { form, email, button: elements['waitlist-submit'], status: elements['waitlist-status'], fields: elements['waitlist-fields'], timeout: () => timer(), advance: seconds => { now += seconds * 1000; } };
}

function response(status = 200, body = { ok: true }, retry = null) {
  return { status, ok: status >= 200 && status < 300, headers: { get: () => retry }, json: async () => body };
}

test('accessible exact copy, placement, labels, privacy and no-JS explanation', () => {
  assert.ok(html.includes("Join the waitlist to get email when it's done and available to purchase"));
  assert.ok(html.indexOf('id="waitlist-form"') > html.indexOf('</header>'));
  assert.ok(html.indexOf('id="waitlist-form"') < html.indexOf('<ol class="timeline">'));
  assert.match(html, /label for="waitlist-email"/);
  assert.match(html, /type="email"[^>]*required/);
  assert.match(html, /role="status" aria-live="polite"/);
  assert.match(html, /<noscript>.*JavaScript is needed/);
  assert.match(html, /sent privately to the project owner/);
  assert.ok(html.includes('action="https://horae-waitlist.borodutch.com/api/waitlist"'));
});

test('loading, duplicate-submit guard, payload and success', async () => {
  let resolve;
  let calls = 0;
  const ui = setup((url, options) => {
    calls++;
    assert.equal(url, ui.form.action);
    assert.equal(options.credentials, 'omit');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { email: 'a.b+tag@example.com', website: '' });
    return new Promise(done => { resolve = done; });
  });
  assert.equal(ui.fields.disabled, false);
  const pending = ui.form.submit();
  assert.equal(ui.button.disabled, true);
  assert.equal(ui.email.readOnly, true);
  assert.match(ui.status.textContent, /Saving/);
  await ui.form.submit();
  assert.equal(calls, 1);
  resolve(response());
  await pending;
  assert.match(ui.status.textContent, /You're on the waitlist/);
  assert.equal(ui.email.value, '');
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.form.attributes['aria-busy'], 'false');
});

test('invalid browser input does not send', async () => {
  const ui = setup(() => assert.fail('must not send'));
  ui.form.reportValidity = () => false;
  await ui.form.submit();
});

test('network failure preserves email and supports retry', async () => {
  let calls = 0;
  const ui = setup(async () => { if (++calls === 1) throw new Error('network'); return response(); });
  await ui.form.submit();
  assert.match(ui.status.textContent, /couldn't confirm/);
  assert.equal(ui.email.value, 'a.b+tag@example.com');
  assert.equal(ui.button.textContent, 'Try again');
  await ui.form.submit();
  assert.match(ui.status.textContent, /You're on the waitlist/);
});

test('rate and storage errors honor Retry-After before user retry', async () => {
  for (const code of [429, 503]) {
    let calls = 0;
    const ui = setup(async () => { calls++; return response(code, {}, '60'); });
    await ui.form.submit();
    assert.match(ui.status.textContent, /60 seconds/);
    await ui.form.submit();
    assert.equal(calls, 1);
    assert.equal(ui.email.value, 'a.b+tag@example.com');
    ui.advance(61);
    await ui.form.submit();
    assert.equal(calls, 2);
  }
});

test('server validation and malformed success never claim signup', async () => {
  for (const result of [response(400), response(500), response(200, { ok: false })]) {
    const ui = setup(async () => result);
    await ui.form.submit();
    assert.doesNotMatch(ui.status.textContent, /You're on/);
    assert.equal(ui.button.textContent, 'Try again');
    assert.equal(ui.email.value, 'a.b+tag@example.com');
  }
});

test('timeout releases UI for safe retry', async () => {
  const ui = setup((_, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error('timeout')));
  }));
  const pending = ui.form.submit();
  ui.timeout();
  await pending;
  assert.match(ui.status.textContent, /couldn't confirm/);
  assert.equal(ui.button.disabled, false);
});
