import { chromium } from 'playwright-core';
// Chemin du navigateur et de la page : surchargeables sans toucher au test.
const EXE = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PAGE = process.env.SAISIO || 'file://' + process.cwd().replace(/\/tool\/tests\/ui$/, '') + '/index.html';
const b = await chromium.launch({ executablePath: EXE });
const p = await b.newPage({viewport:{width:1440,height:900}});
const errs=[]; p.on('pageerror',e=>errs.push('JS: '+e.message));
const R=[]; const t=(n,ok,d='')=>R.push([ok?'OK ':'>>> ANOMALIE',n,d].join(' | '));
await p.goto(PAGE);
await p.click('.js-login button[type=submit]');

// A. fuite d'état du fichier banque entre dossiers (test correct cette fois)
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(200);
await p.setInputFiles('.js-bqfile',{name:'releve_DUPONT.txt',mimeType:'text/plain',buffer:Buffer.from('x')});
await p.waitForTimeout(150);
const visibleApresImport = await p.locator('.js-bqok').isVisible();
await p.click('.js-home'); await p.click('[data-name="BNC_DR_ROUX_2026"]'); await p.waitForTimeout(250);
const encoreVisible = await p.locator('.js-bqok').isVisible();
const nom = encoreVisible ? await p.locator('.js-bqnom').innerText() : '—';
t('fichier banque remis à zéro au changement de dossier', visibleApresImport && !encoreVisible,
  encoreVisible ? `"${nom}" persiste sur un AUTRE dossier` : 'ok');

// B. la ventilation est-elle reprise dans l'export ?
await p.click('.js-home'); await p.click('[data-name="LMNP_DUPONT_2026"]');
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(200);
await p.locator('.js-split').first().click(); await p.waitForTimeout(150);
const ins=p.locator('.split-l input[type=number]');
await ins.nth(0).fill('2000'); await ins.nth(1).fill('1480');
await p.locator('.split-l select').nth(1).selectOption('615');
await p.click('.js-modal-ok'); await p.waitForTimeout(200);
await p.locator('.stp[data-go="5"]').click(); await p.waitForTimeout(150);
await p.click('.js-download'); await p.waitForTimeout(250);
const meta = await p.locator('.js-odmeta').innerText();
t('export : le nombre de lignes est annoncé', /\d+ lignes d'écriture/.test(meta), meta);
// (le contenu réel du fichier est vérifié ligne à ligne dans export.mjs)
await p.click('.js-modal-close');

// C. étape 3 : le badge affiche-t-il le nombre de justificatifs ?
await p.locator('.stp[data-go="3"]').click(); await p.waitForTimeout(150);
const badge3 = await p.locator('.step[data-s="3"] .badge-h .n').innerText();
const nbJust = await p.locator('.ritem').count();
t('badge étape 3 = numéro de section (2), voulu ainsi', badge3==='2',
  `badge="${badge3}" alors qu'il y a ${nbJust} justificatifs`);

// D. Polo : la seule ligne est-elle bien catégorisée ?
await p.click('.js-home'); await p.click('[data-name="LMNP_POLO_TEST"]');
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(200);
const ongletsPolo = (await p.locator('.js-optabs .optab').allInnerTexts()).map(x=>x.replace(/\n/g,''));
const chipsPolo = (await p.locator('.chips i').allInnerTexts()).join(' / ');
t('Polo (sans banque) : aucun motif « sans règlement en banque »',
  !ongletsPolo.some(x=>x.startsWith('Sans règlement')) && !/Sans règlement/.test(chipsPolo),
  ongletsPolo.join(' / ')+(chipsPolo?'  chips: '+chipsPolo:''));

console.log(R.join('\n'));
console.log('\nERREURS JS: '+(errs.length?errs.join('\n'):'aucune'));
await b.close();
