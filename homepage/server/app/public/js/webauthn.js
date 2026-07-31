// 패스키(WebAuthn) 등록/로그인 공용 헬퍼. login.html(로그인)과 account.html(패스키 관리)에서 같이 쓴다.

function isPasskeySupported() {
  return !!(window.PublicKeyCredential && navigator.credentials);
}

function bufferToBase64url(buffer) {
  const bytes = new Uint8Array(buffer);
  let str = '';
  for (const b of bytes) str += String.fromCharCode(b);
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64urlToBuffer(b64url) {
  const pad = (4 - (b64url.length % 4)) % 4;
  const b64 = b64url.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat(pad);
  const str = atob(b64);
  const bytes = new Uint8Array(str.length);
  for (let i = 0; i < str.length; i++) bytes[i] = str.charCodeAt(i);
  return bytes.buffer;
}

function preformatCreationOptions(json) {
  json.challenge = base64urlToBuffer(json.challenge);
  json.user.id = base64urlToBuffer(json.user.id);
  if (json.excludeCredentials) {
    json.excludeCredentials = json.excludeCredentials.map(c => ({ ...c, id: base64urlToBuffer(c.id) }));
  }
  return json;
}

function preformatRequestOptions(json) {
  json.challenge = base64urlToBuffer(json.challenge);
  if (json.allowCredentials) {
    json.allowCredentials = json.allowCredentials.map(c => ({ ...c, id: base64urlToBuffer(c.id) }));
  }
  return json;
}

function serializeRegistrationCredential(cred) {
  return {
    id: cred.id,
    rawId: bufferToBase64url(cred.rawId),
    type: cred.type,
    authenticatorAttachment: cred.authenticatorAttachment || null,
    response: {
      clientDataJSON: bufferToBase64url(cred.response.clientDataJSON),
      attestationObject: bufferToBase64url(cred.response.attestationObject),
      transports: (cred.response.getTransports && cred.response.getTransports()) || [],
    },
    clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
  };
}

function serializeAuthenticationCredential(cred) {
  return {
    id: cred.id,
    rawId: bufferToBase64url(cred.rawId),
    type: cred.type,
    authenticatorAttachment: cred.authenticatorAttachment || null,
    response: {
      clientDataJSON: bufferToBase64url(cred.response.clientDataJSON),
      authenticatorData: bufferToBase64url(cred.response.authenticatorData),
      signature: bufferToBase64url(cred.response.signature),
      userHandle: cred.response.userHandle ? bufferToBase64url(cred.response.userHandle) : null,
    },
    clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
  };
}

// 로그인된 상태에서 새 패스키를 등록한다 (account.html에서 사용).
// 두 단계로 나눈 이유: navigator.credentials.create()는 Safari/WebKit에서 "문서가
// 포커스되어 있지 않다(NotAllowedError: The document is not focused)"는 이유로
// 실패할 수 있는데, 이는 실제로 브라우저 네이티브 prompt()/alert() 같은 블로킹
// 다이얼로그가 닫힌 직후 포커스가 아직 문서로 완전히 돌아오지 않은 상태에서 바로
// WebAuthn을 호출했을 때 흔히 발생한다. 그래서 패스키 이름을 먼저 물어보고 나서
// create()를 부르면 실패하고, 버튼 클릭에 곧바로(다이얼로그 없이) create()부터
// 부르고 이름은 성공한 뒤에 물어봐야 안전하다.
async function createPasskeyCredential() {
  const optRes = await fetch('/api/auth/passkey/register/options', {
    method: 'POST',
    credentials: 'include',
  });
  if (!optRes.ok) {
    const d = await optRes.json().catch(() => ({}));
    throw new Error(d.detail || '패스키 등록 옵션을 가져오지 못했습니다');
  }
  const options = preformatCreationOptions(await optRes.json());
  const credential = await navigator.credentials.create({ publicKey: options });
  return serializeRegistrationCredential(credential);
}

async function verifyPasskeyRegistration(serializedCredential, deviceName) {
  const verifyRes = await fetch('/api/auth/passkey/register/verify', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential: serializedCredential, device_name: deviceName || null }),
  });
  const data = await verifyRes.json();
  if (!verifyRes.ok) throw new Error(data.detail || '패스키 등록에 실패했습니다');
  return data;
}

// 아이디 입력 없이 패스키만으로 로그인한다 (login.html에서 사용). 성공 시 세션 쿠키가
// 설정되고 {token, user}를 반환한다 — 호출부에서 리다이렉트를 처리한다.
async function loginWithPasskey() {
  const optRes = await fetch('/api/auth/passkey/login/options', { method: 'POST' });
  if (!optRes.ok) {
    throw new Error('패스키 로그인 옵션을 가져오지 못했습니다');
  }
  const options = preformatRequestOptions(await optRes.json());

  const credential = await navigator.credentials.get({ publicKey: options });
  const serialized = serializeAuthenticationCredential(credential);

  const verifyRes = await fetch('/api/auth/passkey/login/verify', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential: serialized }),
  });
  const data = await verifyRes.json();
  if (!verifyRes.ok) throw new Error(data.detail || '패스키 로그인에 실패했습니다');
  return data;
}

// 패스키 등록/로그인 실패는 브라우저·기기별 WebAuthn 지원 차이가 원인인 경우가
// 많아 최종 사용자 화면에는 기술적인 내용을 보여주지 않고, 서버 쪽(시스템 오류
// 채널)에만 기록한다.
function reportPasskeyError(context, err) {
  fetch('/api/auth/passkey/client-error', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ context, name: err && err.name, message: err && err.message }),
  }).catch(() => {});
}

// 패스키 이름 입력창의 기본값으로 쓸, navigator.userAgent 기반의 대략적인 기기 이름
// 추측 ("Chrome (Windows)", "Safari (iPhone)" 등). 완벽한 감지가 목적이 아니라
// 사용자가 굳이 직접 타이핑하지 않아도 되게 하는 편의용 기본값이라 휴리스틱이면 충분하다.
function guessDeviceName() {
  const ua = navigator.userAgent || '';

  let os = '기기';
  if (/iPhone/.test(ua)) os = 'iPhone';
  else if (/iPad/.test(ua)) os = 'iPad';
  else if (/Android/.test(ua)) os = 'Android';
  else if (/Mac OS X/.test(ua)) os = 'Mac';
  else if (/Windows/.test(ua)) os = 'Windows';
  else if (/Linux/.test(ua)) os = 'Linux';

  // Edge/Opera/iOS Chrome/iOS Firefox는 UA에 "Chrome"·"Safari"가 같이 들어있으므로
  // 고유 토큰을 먼저 확인해야 한다.
  let browser = '브라우저';
  if (/Edg\//.test(ua)) browser = 'Edge';
  else if (/OPR\//.test(ua) || /Opera/.test(ua)) browser = 'Opera';
  else if (/CriOS\//.test(ua)) browser = 'Chrome';
  else if (/FxiOS\//.test(ua)) browser = 'Firefox';
  else if (/Chrome\//.test(ua)) browser = 'Chrome';
  else if (/Firefox\//.test(ua)) browser = 'Firefox';
  else if (/Safari\//.test(ua) && /Version\//.test(ua)) browser = 'Safari';

  return `${browser} (${os})`;
}

async function listPasskeys() {
  const res = await fetch('/api/auth/passkey/list', { credentials: 'include' });
  if (!res.ok) throw new Error('패스키 목록을 가져오지 못했습니다');
  const data = await res.json();
  return data.passkeys || [];
}

async function deletePasskey(credentialId) {
  const res = await fetch(`/api/auth/passkey/${encodeURIComponent(credentialId)}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '패스키 삭제에 실패했습니다');
  return data;
}
