import { chromium } from 'playwright-core';
// Chemin du navigateur et de la page : surchargeables sans toucher au test.
const EXE = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PAGE = process.env.SAISIO || 'file://' + process.cwd().replace(/\/tool\/tests\/ui$/, '') + '/index.html';
const b = await chromium.launch({ executablePath: EXE });
const p = await b.newPage({viewport:{width:1440,height:900}});
const errs=[]; p.on('pageerror',e=>errs.push('JS: '+e.message));
const R=[]; const t=(n,ok,d='')=>R.push([ok?'OK ':'>>>',n,d].join(' | '));
await p.goto(PAGE);
await p.click('.js-login button[type=submit]');

// --- A. dossier SANS banque (Polo) ---
await p.click('[data-name="LMNP_BERNARD_2025"]'); await p.waitForTimeout(250);
t('Bernard : bascule Banque sur Non', (await p.getAttribute('.lmnp','data-banque'))==='non');
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(200);
t('Bernard : onglets sans « hors relevé »',
  !(await p.locator('.js-wstabs .optab').allInnerTexts()).some(x=>/hors relev/.test(x)),
  (await p.locator('.js-wstabs .optab').allInnerTexts()).map(x=>x.replace(/\n/g,'')).join(' / '));
await p.locator('.stp[data-go="5"]').click(); await p.waitForTimeout(200);
t('sans banque : carte Excel masquée', !(await p.locator('.js-file-xlsx').isVisible()));

// --- B. changement de dossier : fuite d'état ? ---
await p.click('.js-home'); await p.click('[data-name="BNC_DR_ROUX_2026"]'); await p.waitForTimeout(250);
t('BNC : type sélectionné', (await p.locator('.js-type').inputValue())==='bnc');
t('BNC : nom client dans le mail', true, await p.locator('.js-client-name').first().innerText().catch(()=>'?'));
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(200);
t('BNC : onglet réinitialisé sur « Tout »', (await p.locator('.js-wstabs .optab').first().getAttribute('class')).includes('on'));
// le fichier banque importé sur DUPONT reste-t-il affiché ?
await p.locator('.stp[data-go="1"]').click(); await p.waitForTimeout(150);
t('changement de dossier : fichier banque réinitialisé',
  !(await p.locator('.js-bqok').isVisible()), 'un relevé appartient à un seul dossier');

// --- C. décomposition : suppression de ligne, annulation ---
await p.click('.js-home'); await p.click('[data-name="LMNP_DUPONT_2026"]');
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(250);
await p.locator('.oprow', {hasText:'MENUISERIE DES CIMES'}).click(); await p.waitForTimeout(200);
await p.locator('.js-split').click(); await p.waitForTimeout(200);
await p.locator('.split-l .del').last().click(); await p.waitForTimeout(100);
t('suppression de ligne', (await p.locator('.split-l').count())===1,
  'OK désactivé: '+await p.locator('.js-modal-ok').isDisabled());
await p.click('.js-modal-close'); await p.waitForTimeout(150);
t('fermer sans enregistrer : aucune ventilation', (await p.locator('.ventil').count())===0);
// enregistrer puis rouvrir
await p.locator('.js-split').click(); await p.waitForTimeout(200);
const ins=p.locator('.split-l input[type=number]');
await ins.nth(0).fill('2000'); await ins.nth(1).fill('1480'); await p.waitForTimeout(100);
await p.click('.js-modal-ok'); await p.waitForTimeout(200);
t('ventilation enregistrée', (await p.locator('.ventil').count())===1);
t('bouton devient Modifier', (await p.locator('.js-split').innerText()).includes('Modifier'));
await p.locator('.js-split').click(); await p.waitForTimeout(200);
const vals=await p.locator('.split-l input[type=number]').evaluateAll(n=>n.map(x=>x.value));
t('réouverture pré-remplie', JSON.stringify(vals)==='["2000.00","1480.00"]', vals.join('/'));
await p.click('.js-modal-close');

// --- D. persistance après changement d'étape ---
await p.locator('.stp[data-go="4"]').click(); await p.waitForTimeout(120);
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(150);
t('ventilation survit au changement d\'étape', (await p.locator('.ventil').count())===1);

// --- E. saisie de compte : annulation / champ vide ---
// (sur une ligne NON ventilée : une facture décomposée n'a plus de compte unique)
await p.locator('.oprow', {hasText:'BOULANGER'}).click(); await p.waitForTimeout(250);
t('une facture ventilée n\'a pas de compte unique', await p.evaluate(()=>{
  const r=[...document.querySelectorAll('.oprow')].find(x=>/MENUISERIE/.test(x.textContent));
  r.click(); const sel=document.querySelectorAll('.js-imput').length;
  const ven=document.querySelectorAll('.ventil span').length;
  [...document.querySelectorAll('.oprow')].find(x=>/BOULANGER/.test(x.textContent)).click();
  return sel===0 && ven===2;}));
await p.waitForTimeout(250);
const avant=await p.locator('.js-imput').inputValue();
await p.locator('.js-imput').selectOption('__autre__'); await p.waitForTimeout(200);
await p.click('.js-modal-ok'); await p.waitForTimeout(150);
t('compte vide : fenêtre reste ouverte', await p.locator('.js-modal.on').isVisible());
await p.click('.js-modal-close'); await p.waitForTimeout(200);
const apres=await p.locator('.js-imput').inputValue();
t('annulation : le select ne reste pas sur « Autre compte »', apres!=='__autre__', `${avant} -> ${apres}`);

// --- F. déconnexion ? ---
t('bouton de déconnexion présent', (await p.locator('.js-logout').count())===1);

// --- G. étape 3 : tout décocher ---
await p.locator('.stp[data-go="3"]').click(); await p.waitForTimeout(150);
const n=await p.locator('.ritem').count();
for(let i=0;i<n;i++){ await p.locator('.ritem').nth(i).click(); }
await p.waitForTimeout(150);
while(await p.getAttribute('.lmnp','data-step')==='3'){
  await p.click('.js-recvalider'); await p.waitForTimeout(180); }
await p.waitForTimeout(1); await p.waitForTimeout(200);
t('mail avec 0 justificatif', true,
  'lignes='+await p.locator('.js-mail-list li').count()+' | objet mentionne '+
  (await p.locator('.js-mail-n').first().innerText()));

console.log(R.join('\n'));
console.log('\nERREURS JS: '+(errs.length?errs.join('\n'):'aucune'));
await b.close();
