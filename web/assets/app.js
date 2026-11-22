'use strict';
(function () {
  const E = window.ethers;
  const $ = (id) => document.getElementById(id);
  const st = { cfg: null, scan: null, quote: null, safe: null, tsToken: null, tsLoaded: false };

  function show(el, lines, cls) {
    el.textContent = '';
    el.className = 'out' + (cls ? ' ' + cls : '');
    for (const l of [].concat(lines)) { const p = document.createElement('div'); p.textContent = l; el.appendChild(p); }
  }
  // ORDEN #1258: Arbitrum (42161) se sirve en /arb/api/ (unsweep-relayer-arb); Base y Ethereum read-only en /api/.
  const CHAIN_IDS = { base: 8453, arbitrum: 42161 };
  function apiBase() { return ($('chain') && $('chain').value === 'arbitrum') ? '/arb/api/' : '/api/'; }
  async function api(path, body) {
    const r = await fetch(apiBase() + path, body ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) } : {});
    let j = null; try { j = await r.json(); } catch (e) { /* noop */ }
    if (!r.ok) throw new Error((j && j.detail) ? String(j.detail) : ('HTTP ' + r.status));
    return j;
  }
  // #985: unverified extras, unchecked by default; names rendered as text only
  function renderExtras(list) {
    const box = $('extrasBox'), ul = $('extrasList'); if (!box || !ul) return;
    ul.textContent = '';
    for (const x of list.slice(0, 20)) {
      const a = addr(x.address); if (!a) continue;
      const lab = document.createElement('label'); lab.className = 'small';
      const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = false; cb.value = a; cb.className = 'extraCb';
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(' ' + String(x.symbol || '?').slice(0, 24) + ' ' + a + ': ' + fmt(x.balance, x.decimals)));
      const d = document.createElement('div'); d.appendChild(lab); ul.appendChild(d);
    }
    box.hidden = ul.childNodes.length === 0;
  }
  function checkedExtras() { return Array.from(document.querySelectorAll('#extrasList .extraCb')).filter((c) => c.checked).map((c) => c.value); }
  function addr(v) { try { return E.getAddress(String(v).trim()); } catch (e) { return null; } }
  function fmt(amount, dec) { try { return E.formatUnits(BigInt(amount), Number(dec)); } catch (e) { return String(amount); } }

  // ---------- STEP 1: scan (public address only) ----------
  $('btnScan').addEventListener('click', () => { runScan(); });
  async function scanImpl() {
    const a = addr($('victim').value);
    if (!a) return show($('scanOut'), 'Invalid address.', 'err');
    const chain = ($('chain') && $('chain').value) || 'testnet';
    goStep(1); $('btnToStep2').hidden = true;
    if (chain === 'ethereum') {
      st.scan = null; // rescue is never enabled on mainnet
      show($('scanOut'), 'Read-only check on ' + (chain === 'base' ? 'Base' : 'Ethereum') + ' mainnet...');
      try {
        const m = await api('scan', { address: a, chain: chain });
        const d = m.delegation7702 || {};
        const nat = m.native || {};
        const complete = m.status === 'complete';
        const out = [];
        if (!complete) {
          out.push('Incomplete check — this is NOT a clean result.');
          for (const r of (m.incompleteReasons || ['the server did not confirm that every query finished'])) out.push('Reason: ' + r);
          out.push('Some data could not be verified. Try again in a minute; do not assume this wallet is safe.');
        }
        out.push('Network: ' + chain + ' mainnet (read-only, nothing was signed)', 'Address: ' + a, 'Nonce: ' + m.nonce,
          'EIP-7702 delegation: ' + (d.active ? ('ACTIVE -> ' + d.delegate + ' (verify this contract; an unknown delegate may be a sweeper)') : (d.active === false ? 'none' : 'unknown (check failed)')),
          (nat.symbol || 'ETH') + ': ' + (nat.balanceWei == null ? 'unknown' : fmt(nat.balanceWei, 18)));
        const toks = m.tokens || [];
        if (toks.length === 0 && complete) out.push('No ERC-20 balances found.');
        for (const t of toks) out.push('Token ' + (t.symbol || t.contract || t.address || t.token) + ': ' + (t.balanceFmt || fmt(t.balance || t.balanceRaw || '0', t.decimals == null ? 18 : t.decimals)));
        const aps = m.approvals || [];
        if (aps.length === 0 && complete) out.push('No open ERC-20 approvals found from direct approve transactions in the last 90 days.');
        for (const ap of aps) out.push('Open approval: ' + (ap.symbol || ap.token) + ' -> spender ' + ap.spender + (ap.unlimited ? ' (unlimited)' : '') + ' - see /guides/revoke-approvals/');
        const am = m.approvalsMeta || {};
        if (!complete) out.push('Approvals listed above may be partial (' + (am.txScanned || 0) + ' recent transactions checked).');
        out.push('Ethereum mainnet: read-only check. Rescue is currently live on Base mainnet (16 verified ERC-20 tokens) and Arbitrum mainnet (12 verified ERC-20 tokens).');
        show($('scanOut'), out, complete ? 'ok' : 'err');
      } catch (e) { show($('scanOut'), 'Scan failed: ' + e.message, 'err'); }
      return;
    }
    // #1152/#1175: indicador por fases y tiempo real transcurrido. /api/scan es un unico POST sin
    // progreso en servidor: la fase mostrada es orientativa (por tiempo); NO se muestra contador ni porcentaje.
    const scanProg = (function () {
      const t0 = Date.now();
      const tick = function () {
        const el = Math.floor((Date.now() - t0) / 1000); let phase;
        if (el < 3) phase = 'Checking balances and delegation';
        else if (el < 30) phase = 'Scanning approval history on Base';
        else phase = ['Still scanning (long histories take longer)', 'Reading older approval logs', 'Cross-checking open approvals'][Math.floor(el / 5) % 3];
        show($('scanOut'), phase + '… ' + el + ' s elapsed');
      };
      tick(); const h = setInterval(tick, 1000);
      return { stop: function () { clearInterval(h); } };
    })();
    try {
      if (!st.cfg || st.cfgChain !== chain) {
        st.cfg = await api('config'); st.cfgChain = chain;
        if (CHAIN_IDS[chain] && Number(st.cfg.chainId) !== CHAIN_IDS[chain]) { st.cfg = null; st.cfgChain = null; scanProg.stop(); return show($('scanOut'), 'Network mismatch from server. Please reload the page and try again.', 'err'); }
      }
      let s; try { s = await api('scan', { address: a }); } finally { scanProg.stop(); }
      st.scan = s;
      const out = ['Address: ' + s.address, 'ETH: ' + E.formatEther(BigInt(s.eth_wei)), 'Nonce: ' + s.nonce,
        'EIP-7702 delegation: ' + (s.delegation7702 || 'none')];
      if (s.tokens.length === 0 && s.nfts.length === 0) out.push('No rescuable tokens found in our list.');
      for (const t of s.tokens) out.push('Token ' + (t.symbol || t.address) + ': ' + fmt(t.balance, t.decimals));
      for (const n of s.nfts) out.push('NFT ' + (n.symbol || n.address) + ' #' + n.id);
      for (const ap of (s.approvals || [])) out.push('Live approval: ' + ap.token + ' -> ' + ap.spender + ' (revoke recommended)');
      show($('scanOut'), out, 'ok');
      renderExtras(s.extras || []);
      if (s.rescuable) $('btnToStep2').hidden = false;
    } catch (e) { show($('scanOut'), 'Scan failed: ' + e.message, 'err'); }
  }

  // ---------- STEP 2: simulation ----------
  // @@typed-begin (pure; evaluated by relayer/test_typehash_parity.py)
  function unsweepTyped(E, r, chainId, victim) {
    const c = E.AbiCoder.defaultAbiCoder();
    const types = { Rescue: [{ name: 'safe', type: 'address' }, { name: 'callsHash', type: 'bytes32' },
      { name: 'tokensHash', type: 'bytes32' }, { name: 'nftsHash', type: 'bytes32' }, { name: 'maxFeeBps', type: 'uint16' },
      { name: 'minFeesHash', type: 'bytes32' }, { name: 'nonce', type: 'uint256' }, { name: 'deadline', type: 'uint256' }] };
    const msg = { safe: r.safe,
      callsHash: E.keccak256(c.encode(['tuple(address,uint256,bytes)[]'], [r.calls])),
      tokensHash: E.keccak256(c.encode(['address[]'], [r.tokens])),
      nftsHash: E.keccak256(c.encode(['tuple(address,uint256)[]'], [r.nfts])),
      maxFeeBps: r.maxFeeBps, minFeesHash: E.keccak256(c.encode(['uint256[]'], [r.minFees])),
      nonce: r.nonce, deadline: r.deadline };
    const domain = { name: 'Unsweep', version: '1', chainId: chainId, verifyingContract: victim };
    return { domain, types, msg };
  }
  // @@typed-end

  $('btnQuote').addEventListener('click', async () => {
    const safe = addr($('safe').value);
    if (!safe || !st.scan) return show($('quoteOut'), 'Invalid safe address.', 'err');
    if (safe === st.scan.address) return show($('quoteOut'), 'The safe wallet must be different.', 'err');
    show($('quoteOut'), 'Simulating...');
    $('step3').hidden = true; $('btnToStep3').hidden = true;
    try {
      const r = await api('quote', { address: st.scan.address, safe: safe, extras: checkedExtras() });
      const q = r.quote; st.quote = q; st.safe = safe; st.scan = r.scan;
      const tierBps = Number(q.maxFeeBps != null ? q.maxFeeBps : q.feeBps); st.shownBps = tierBps;
      const out = ['Fee tier: ' + (tierBps / 100) + '% (maximum signed by you; taken in kind from the rescued tokens).'];
      for (const l of q.lines) out.push((l.unverified ? '[unverified] ' : '') + (l.symbol || l.token) + ': total ' + fmt(l.amount, l.decimals) + ' | fee ' + fmt(l.fee, l.decimals) + ' | you receive ' + fmt(l.net, l.decimals));
      if (checkedExtras().length && q.extras_reason) out.push('Unverified tokens excluded: ' + q.extras_reason);
      if (q.nfts > 0) out.push('NFTs found: ' + q.nfts + ' (NFT rescue is not enabled in this preview; they are excluded).');
      const netUsd = Math.max(0, Number(q.rescued_usd) - Number(q.fee_usd));
      out.push('Estimated value: $' + q.rescued_usd);
      out.push('Fee: $' + q.fee_usd + ' (' + q.fee_pct + '% of the rescued value; tier ' + (tierBps / 100) + '%)');
      out.push('Your safe wallet receives: ~$' + netUsd.toFixed(2) + ' (per token amounts above).');
      if (!q.policy_ok) { out.push('Not eligible: ' + q.policy_reason); return show($('quoteOut'), out, 'err'); }
      if (q.lines.length === 0) { out.push('Nothing to rescue.'); return show($('quoteOut'), out, 'err'); }
      show($('quoteOut'), out, 'ok');
      $('btnToStep3').hidden = false;
    } catch (e) { show($('quoteOut'), 'Simulation failed: ' + e.message, 'err'); }
  });

  // ---------- Turnstile (explicit render, only at step 3) ----------
  function loadTurnstile() {
    if (st.tsLoaded) return; st.tsLoaded = true;
    const sc = document.createElement('script');
    sc.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    sc.async = true;
    sc.addEventListener('load', () => {
      window.turnstile.render('#ts', { sitekey: st.cfg.turnstileSitekey, callback: (t) => { st.tsToken = t; },
        'expired-callback': () => { st.tsToken = null; } });
    });
    document.head.appendChild(sc);
  }

  // ---------- STEP 3: local signing ----------
  function readKey() {
    const el = $('pk'); const raw = String(el.value || '').trim();
    el.value = ''; // the key never stays in the DOM
    if (raw.split(/\s+/).length >= 2) throw new Error('This looks like a seed phrase. Seed phrases are rejected: never share them with anyone.');
    if (!/^(0x)?[0-9a-fA-F]{64}$/.test(raw)) throw new Error('Invalid private key format (expected 64 hex characters).');
    return raw.startsWith('0x') ? raw : '0x' + raw;
  }
  function randNonce() { const b = new Uint32Array(2); crypto.getRandomValues(b); return ((BigInt(b[0]) << 32n) | BigInt(b[1])).toString(); }

  $('btnRescue').addEventListener('click', async () => {
    const out = $('rescueOut');
    if (!st.quote || !st.safe) return show(out, 'Run steps 1 and 2 first.', 'err');
    if (!st.tsToken) return show(out, 'Please complete the anti-bot check.', 'err');
    let w = null;
    try {
      w = new E.Wallet(readKey());
      const victim = st.scan.address;
      if (w.address !== victim) throw new Error('This key does not belong to the scanned address.');
      const chainId = Number(st.cfg.chainId);
      // 1) EIP-7702 authorization delegating to UnsweepDelegate (signed locally)
      const au = w.authorizeSync({ address: st.cfg.delegate, nonce: BigInt(st.scan.nonce), chainId: BigInt(chainId) });
      const sa = au.signature;
      // 2) EIP-712 Rescue (verifyingContract = the compromised EOA itself)
      const tokens = st.quote.lines.map((l) => E.getAddress(l.token));
      const q = st.quote;
      const maxFeeBps = Number(q.maxFeeBps != null ? q.maxFeeBps : q.feeBps);
      const minFees = q.lines.some((l) => l.minFee != null) ? q.lines.map((l) => String(l.minFee || '0')) : [];
      if (maxFeeBps !== st.shownBps) throw new Error('Fee tier changed since the simulation; simulate again.');
      const rescue = { safe: st.safe, calls: [], tokens: tokens, nfts: [],
        maxFeeBps: maxFeeBps, minFees: minFees, nonce: randNonce(), deadline: String(Math.floor(Date.now() / 1000) + 600) };
      const { domain, types, msg } = unsweepTyped(E, rescue, chainId, victim);
      const sig = E.Signature.from(await w.signTypedData(domain, types, msg));
      w = null; // drop the key from memory as soon as signing is done
      const body = { turnstile: st.tsToken,
        auth: { chainId: chainId, nonce: String(st.scan.nonce), address: st.cfg.delegate, yParity: sa.yParity, r: sa.r, s: sa.s },
        rescue: rescue, v: sig.v, r: sig.r, s: sig.s };
      show(out, 'Signed locally. Sending signatures only to the relayer...');
      const res = await api('rescue', body);
      show(out, ['Status: ' + res.status, 'Tx: ' + res.txHash, res.explorer], res.status === 'success' ? 'ok' : 'err');
    } catch (e) {
      w = null;
      show(out, 'Rescue failed: ' + e.message, 'err');
    } finally {
      st.tsToken = null; if (window.turnstile) { try { window.turnstile.reset('#ts'); } catch (e) { /* noop */ } }
    }
  });
  // #1194: wizard (only the active step visible; completed steps collapsed with Edit)
  function goStep(n) {
    for (let i = 1; i <= 3; i++) {
      const sec = $('step' + i), body = $('step' + i + 'Body'), done = $('step' + i + 'Done');
      if (sec) sec.hidden = i > n;
      if (body) body.hidden = i !== n;
      if (done) done.hidden = !(i < n);
    }
    const s = $('step' + n); if (s && s.scrollIntoView) s.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }
  async function runScan() {
    const b = $('btnScan'); if (b.disabled) return;
    const label = b.textContent, t0 = Date.now();
    b.disabled = true; b.setAttribute('aria-busy', 'true');
    const paint = function () { b.textContent = ''; const sp = document.createElement('span'); sp.className = 'spinner'; sp.setAttribute('aria-hidden', 'true'); b.appendChild(sp); b.appendChild(document.createTextNode(' Scanning\u2026')); };
    paint(); const h = null;
    try { await scanImpl(); } finally { clearInterval(h); b.disabled = false; b.removeAttribute('aria-busy'); b.textContent = label; }
  }
  $('btnToStep2').addEventListener('click', () => {
    $('step1Sum').textContent = 'Wallet ' + (st.scan ? st.scan.address : '') + ' (' + ($('chain') ? $('chain').value : '') + ')';
    goStep(2);
  });
  $('btnToStep3').addEventListener('click', () => {
    $('step2Sum').textContent = 'Destination ' + (st.safe || '');
    goStep(3); loadTurnstile();
  });
  $('edit1').addEventListener('click', () => goStep(1));
  $('edit2').addEventListener('click', () => goStep(2));
  $('pkToggle').addEventListener('click', () => {
    const i = $('pk'), t = $('pkToggle'), vis = i.type === 'password';
    i.type = vis ? 'text' : 'password'; t.textContent = vis ? 'Hide' : 'Show'; t.setAttribute('aria-pressed', vis ? 'true' : 'false');
  });
})();
