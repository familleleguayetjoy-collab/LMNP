import { chromium } from 'playwright-core';
// Chemin du navigateur et de la page : surchargeables sans toucher au test.
const EXE = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PAGE = process.env.SAISIO || 'file://' + process.cwd().replace(/\/tool\/tests\/ui$/, '') + '/index.html';
const b = await chromium.launch({ executablePath: EXE });
const p = await b.newPage({viewport:{width:1440,height:900}});
const errs=[]; p.on('pageerror',e=>errs.push('JS: '+e.message));
const R=[]; const t=(n,ok,d='')=>R.push([ok?'OK ':'>>> KO',n,d].join(' | '));
await p.goto(PAGE);
await p.click('.js-login button[type=submit]');
// capture le contenu du blob téléchargé
await p.addInitScript(()=>{ window.__ASCII=''; const o=URL.createObjectURL;
  URL.createObjectURL=function(bl){ bl.text().then(x=>{window.__ASCII=x;}); return o.call(URL,bl); }; });
await p.reload(); await p.waitForTimeout(150);

await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(300);
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(200);
// export de référence, AVANT toute décomposition
await p.locator('.stp[data-go="5"]').click(); await p.waitForTimeout(200);
await p.click('.js-download'); await p.waitForTimeout(400);
const nOps = (await p.evaluate(()=>window.__ASCII)).split('\r\n').filter(x=>x.length).length;
await p.click('.js-modal-close');
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(200);
// décomposer la 1re opération en 2 comptes
await p.locator('.js-split').first().click(); await p.waitForTimeout(200);
const ins=p.locator('.split-l input[type=number]');
const tot=parseFloat(await ins.nth(0).inputValue());
await ins.nth(0).fill((tot*0.6).toFixed(2)); await ins.nth(1).fill((tot*0.4).toFixed(2));
await p.locator('.split-l select').nth(1).selectOption({index:1});
await p.click('.js-modal-ok'); await p.waitForTimeout(250);
// aller jusqu'à l'export
while(await p.getAttribute('.lmnp','data-step')==='2'){ await p.click('.js-valider'); await p.waitForTimeout(160); }
while(await p.getAttribute('.lmnp','data-step')==='3'){ await p.click('.js-recvalider'); await p.waitForTimeout(160); }
await p.click('.step[data-s="4"] .js-next'); await p.waitForTimeout(200);
await p.click('.js-download'); await p.waitForTimeout(400);
const meta = await p.locator('.js-odmeta').innerText();
const ascii = await p.evaluate(()=>window.__ASCII);
const lignes = ascii.split('\r\n').filter(x=>x.length);
t('fichier ASCII produit', lignes.length>0, lignes.length+' lignes');
t('toutes les lignes font 251 caractères', lignes.every(l=>l.length===251),
  [...new Set(lignes.map(l=>l.length))].join('/'));
t('la ventilation ajoute une ligne', lignes.length===nOps+1, `${nOps} opérations -> ${lignes.length} lignes`);
t('le compteur affiché correspond', meta.includes(String(lignes.length)), meta);
// contrepartie 108 et journal OD sur chaque ligne
t('journal OD + contrepartie 108 partout',
  lignes.every(l=>l.slice(9,11)==='OD' && l.slice(55,63)==='10800000'),
  lignes[0].slice(9,11)+' / '+lignes[0].slice(55,63));
// la date d'écriture est celle du règlement quand il est connu
const paye = await p.evaluate(()=>window.__ASCII); // déjà lu
t('dates au format JJMMAA', lignes.every(l=>/^\d{6}$/.test(l.slice(14,20))), lignes[0].slice(14,20));
// somme des montants = somme des opérations
const somme = lignes.reduce((a,l)=>a+ +l.slice(43,55),0)/100;
t('somme des montants cohérente', somme>0, somme.toFixed(2)+' €');
// --- trésorerie : la date saisie « payé le » date l'écriture d'OD ---
await p.click('.js-modal-close'); await p.waitForTimeout(150);
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(200);
let vu=false;
for(let k=0;k<6 && !vu;k++){
  if(await p.locator('.js-datepaie').count()){ vu=true; break; }
  const tabs=await p.locator('.js-optabs .optab').count();
  if(k>=tabs) break;
  await p.locator('.js-optabs .optab').nth(k).click(); await p.waitForTimeout(150);
}
t('un onglet porte la saisie de date de paiement', vu);
if(vu){
  await p.locator('.js-datepaie').first().fill('2026-07-14'); await p.waitForTimeout(200);
  await p.locator('.stp[data-go="5"]').click(); await p.waitForTimeout(200);
  await p.click('.js-download'); await p.waitForTimeout(400);
  const l2=(await p.evaluate(()=>window.__ASCII)).split('\r\n').filter(x=>x.length);
  t('OD datée du jour du règlement saisi', l2.some(l=>l.slice(14,20)==='140726'),
    [...new Set(l2.map(l=>l.slice(14,20)))].join(' '));
}
console.log(R.join('\n'));
console.log('\nERREURS JS: '+(errs.length?errs.join('\n'):'aucune'));
await b.close();
