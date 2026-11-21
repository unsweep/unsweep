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
  async function api(path, body) {
    const r = await fetch('/api/' + path, body ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) } : {});
    let j = null; try { j = await r.json(); } catch (e) { /* noop */ }
    if (!r.ok) throw new Error((j && j.detail) ? String(j.detail) : ('HTTP ' + r.status));
    return j;
  }
  function addr(v) { try { return E.getAddress(String(v).trim()); } catch (e) { return null; } }
  function fmt(amount, dec) { try { return E.formatUnits(BigInt(amount), Number(dec)); } catch (e) { return String(amount); } }

  // ---------- STEP 1: scan (public address only) ----------
  $('btnScan').addEventListener('click', async () => {
    const a = addr($('victim').value);
    if (!a) return show($('scanOut'), 'Invalid address.', 'err');
    const chain = ($('chain') && $('chain').value) || 'testnet';
    $('step2').hidden = true; $('step3').hidden = true;
    if (chain === 'base' || chain === 'ethereum') {
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
        out.push('Mainnet: read-only check. Rescue is testnet beta only.');
        show($('scanOut'), out, complete ? 'ok' : 'err');
      } catch (e) { show($('scanOut'), 'Scan failed: ' + e.message, 'err'); }
      return;
    }
    show($('scanOut'), 'Scanning Base Sepolia... (can take ~30 s)');
    try {
      if (!st.cfg) st.cfg = await api('config');
      const s = await api('scan', { address: a });
      st.scan = s;
      const out = ['Address: ' + s.address, 'ETH: ' + E.formatEther(BigInt(s.eth_wei)), 'Nonce: ' + s.nonce,
        'EIP-7702 delegation: ' + (s.delegation7702 || 'none')];
      if (s.tokens.length === 0 && s.nfts.length === 0) out.push('No rescuable tokens found in our list.');
      for (const t of s.tokens) out.push('Token ' + (t.symbol || t.address) + ': ' + fmt(t.balance, t.decimals));
      for (const n of s.nfts) out.push('NFT ' + (n.symbol || n.address) + ' #' + n.id);
      for (const ap of (s.approvals || [])) out.push('Live approval: ' + ap.token + ' -> ' + ap.spender + ' (revoke recommended)');
      show($('scanOut'), out, 'ok');
      if (s.rescuable) $('step2').hidden = false;
    } catch (e) { show($('scanOut'), 'Scan failed: ' + e.message, 'err'); }
  });

  // ---------- STEP 2: simulation ----------
  $('btnQuote').addEventListener('click', async () => {
    const safe = addr($('safe').value);
    if (!safe || !st.scan) return show($('quoteOut'), 'Invalid safe address.', 'err');
    if (safe === st.scan.address) return show($('quoteOut'), 'The safe wallet must be different.', 'err');
    show($('quoteOut'), 'Simulating...');
    $('step3').hidden = true;
    try {
      const r = await api('quote', { address: st.scan.address, safe: safe });
      const q = r.quote; st.quote = q; st.safe = safe; st.scan = r.scan;
      const out = ['Fee: ' + (q.feeBps / 100) + '% of each rescued token, taken in kind.'];
      for (const l of q.lines) out.push((l.symbol || l.token) + ': total ' + fmt(l.amount, l.decimals) + ' | fee ' + fmt(l.fee, l.decimals) + ' | you receive ' + fmt(l.net, l.decimals));
      if (q.nfts > 0) out.push('NFTs found: ' + q.nfts + ' (NFT rescue is not enabled in this preview; they are excluded).');
      out.push('Estimated value (testnet prices): $' + q.rescued_usd + ' | fee: $' + q.fee_usd);
      if (!q.policy_ok) { out.push('Not eligible: ' + q.policy_reason); return show($('quoteOut'), out, 'err'); }
      if (q.lines.length === 0) { out.push('Nothing to rescue.'); return show($('quoteOut'), out, 'err'); }
      show($('quoteOut'), out, 'ok');
      $('step3').hidden = false; loadTurnstile();
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
      const coder = E.AbiCoder.defaultAbiCoder();
      const tokens = st.quote.lines.map((l) => E.getAddress(l.token));
      const q = st.quote;
      const maxFeeBps = Number(q.maxFeeBps != null ? q.maxFeeBps : q.feeBps);
      const minFees = q.lines.some((l) => l.minFee != null) ? q.lines.map((l) => String(l.minFee || '0')) : [];
      const rescue = { safe: st.safe, calls: [], tokens: tokens, nfts: [], maxNftFee: String(q.maxNftFee || '0'),
        maxFeeBps: maxFeeBps, minFees: minFees, nonce: randNonce(), deadline: String(Math.floor(Date.now() / 1000) + 600) };
      const msg = {
        safe: rescue.safe,
        callsHash: E.keccak256(coder.encode(['tuple(address,uint256,bytes)[]'], [[]])),
        tokensHash: E.keccak256(coder.encode(['address[]'], [tokens])),
        nftsHash: E.keccak256(coder.encode(['tuple(address,uint256)[]'], [[]])),
        maxNftFee: rescue.maxNftFee, maxFeeBps: rescue.maxFeeBps,
        minFeesHash: E.keccak256(coder.encode(['uint256[]'], [minFees])), nonce: rescue.nonce, deadline: rescue.deadline };
      const types = { Rescue: [{ name: 'safe', type: 'address' }, { name: 'callsHash', type: 'bytes32' }, { name: 'tokensHash', type: 'bytes32' },
        { name: 'nftsHash', type: 'bytes32' }, { name: 'maxNftFee', type: 'uint256' },
        { name: 'maxFeeBps', type: 'uint16' }, { name: 'minFeesHash', type: 'bytes32' }, { name: 'nonce', type: 'uint256' }, { name: 'deadline', type: 'uint256' }] };
      const domain = { name: 'Unsweep', version: '1', chainId: chainId, verifyingContract: victim };
      const sig = E.Signature.from(await w.signTypedData(domain, types, msg));
      w = null; // drop the key from memory as soon as signing is done
      const Z = '0x' + '00'.repeat(32);
      const body = { turnstile: st.tsToken,
        auth: { chainId: chainId, nonce: String(st.scan.nonce), address: st.cfg.delegate, yParity: sa.yParity, r: sa.r, s: sa.s },
        rescue: rescue, permit: { value: '0', deadline: '0', v: 0, r: Z, s: Z }, v: sig.v, r: sig.r, s: sig.s };
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
})();
