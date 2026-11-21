"""Descarga el SDN oficial de OFAC y extrae las direcciones ETH (Digital Currency Address - ETH).
Fuente: https://www.treasury.gov/ofac/downloads/sdn.xml
Escritura atomica en relayer/data/ofac_eth.json. Si falla, NO sobrescribe la lista previa.
El relayer es fail-closed: lista ausente/vacia/caducada => rechaza."""
import json, os, re, sys, tempfile, urllib.request, xml.etree.ElementTree as ET, datetime
URL = 'https://www.treasury.gov/ofac/downloads/sdn.xml'
OUT = os.path.join(os.path.dirname(__file__), 'data', 'ofac_eth.json')
ADDR = re.compile(r'^0x[0-9a-fA-F]{40}$')

def main():
    req = urllib.request.Request(URL, headers={'User-Agent': 'unsweep-ofac/1.0'})
    raw = urllib.request.urlopen(req, timeout=120).read()
    root = ET.fromstring(raw)
    ns = {'s': root.tag.split('}')[0].strip('{')}
    pub = root.findtext('s:publshInformation/s:Publish_Date', namespaces=ns)
    addrs = set()
    for idn in root.iterfind('.//s:id', ns):
        if (idn.findtext('s:idType', namespaces=ns) or '').strip() == 'Digital Currency Address - ETH':
            v = (idn.findtext('s:idNumber', namespaces=ns) or '').strip()
            if ADDR.match(v):
                addrs.add(v.lower())
    if len(addrs) < 50:
        sys.exit(f'lista sospechosamente corta ({len(addrs)}); no se sobrescribe')
    data = {'source': URL, 'publish_date': pub,
            'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'count': len(addrs), 'addresses': sorted(addrs)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT))
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, OUT)
    print('ok', pub, len(addrs))

if __name__ == '__main__':
    main()
