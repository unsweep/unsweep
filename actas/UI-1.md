# UI-1 portada unsweep.com (2026-11-21)
- Solo web/index.html y web/assets/style.css; relayer, escáner, contrato y app.js sin cambios.
- CSP antes/después idéntica (curl -sI).
- axe-core 4.14.1 wcag2a/wcag2aa: 0 violaciones en escritorio y móvil (360px), 38 nodos color-contrast OK; contraste manual mínimo 9.16:1; botón deshabilitado 10.48:1.
- Placeholder del campo 0x del paso 1 completo en escritorio y móvil.
- E2E Base Sepolia: tx 0x67a1d97e6864e746bc18c08d9856114f9d4007cac21e5e8233c737e528c3bb24 status 0x1, bloque 61567865, gasUsed 113280; víctima 300 tUSDC/100 tGOV -> 0; segura +255/+85; comisión +45/+15.
- Mint de prueba previo (testnet): 0x7adb80cb..., 0x26ce8fe0...
