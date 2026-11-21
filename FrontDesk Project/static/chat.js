let conversationId = null;
const messagesEl = document.getElementById('messages');
const form = document.getElementById('form');
const input = document.getElementById('input');
const send = document.getElementById('send');
// Uploaded brand logo (Admin -> Settings) passed as a data attribute; '' = default badge.
const logoUrl = messagesEl.dataset.logo || '';
function assistantAvatar() {
  const avatar = document.createElement('span');
  avatar.className = 'ai-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  if (logoUrl.startsWith('/brand/logo/')) {
    avatar.classList.add('ai-avatar-logo');
    const img = document.createElement('img');
    img.src = logoUrl; img.alt = '';
    img.className = 'w-full h-full object-cover object-center';
    img.addEventListener('error', () => { avatar.classList.remove('ai-avatar-logo'); avatar.textContent = 'AI'; });
    avatar.appendChild(img);
  } else {
    avatar.textContent = 'AI';
  }
  return avatar;
}
function addMessage(role, text) {
  const row = document.createElement('div');
  row.className = 'flex gap-2 ' + (role === 'user' ? 'justify-end' : 'justify-start');
  const bubble = document.createElement('div');
  bubble.className = 'max-w-[88%] sm:max-w-[78%] px-4 py-3 text-[13px] leading-relaxed rounded-xl whitespace-pre-wrap break-words ' + (role === 'user' ? 'bg-[#5064eb] text-white rounded-tr-sm' : 'bg-white border border-slate-100 text-[#33415c] rounded-tl-sm');
  bubble.textContent = text;
  if (role !== 'user') row.appendChild(assistantAvatar());
  row.appendChild(bubble); messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}
// Appointment length from Admin -> Settings, passed as a data attribute (default 60).
const appointmentMinutes = /^\d{1,3}$/.test(messagesEl.dataset.minutes || '') ? messagesEl.dataset.minutes : '60';
addMessage('assistant', 'Welcome. I can answer your questions and help request a ' + appointmentMinutes + '-minute appointment. What would you like to do?');
document.querySelectorAll('[data-message]').forEach(b => b.addEventListener('click', () => { input.value = b.dataset.message; input.focus(); }));
input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
form.addEventListener('submit', async e => {
  e.preventDefault(); const text = input.value.trim(); if (!text) return;
  addMessage('user', text); input.value = ''; send.disabled = true; send.textContent = 'Sending…';
  try {
    const body = new FormData(); body.append('message', text);
    if (conversationId) body.append('conversation_id', conversationId);
    const res = await fetch('/chat', { method: 'POST', body });
    const contentType = res.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await res.json() : {};
    if (!res.ok) throw new Error(data.detail || 'The receptionist could not respond. Please try again.');
    conversationId = data.conversation_id;
    addMessage('assistant', data.reply || 'Please try again.');
  } catch (err) { addMessage('assistant', err.message); }
  finally { send.disabled = false; send.textContent = 'Send →'; input.focus(); }
});
