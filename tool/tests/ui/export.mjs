import { chromium } from 'playwright-core';
// Le fichier RÉELLEMENT produit : c'est lui qui part dans Quadra.
const EXE = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PAGE = process.env.SAISIO || 'file://' + process.cwd().replace(/\/tool\/tests\/ui$/, '') + '/index.html';
const b = await chromium.launch({ executablePath: EXE });
const p = await b.newPage({viewport:{width:1440,height:900}});
const errs=[]; p.on('pageerror',e=>errs.push('JS: '+e.message));
const R=[]; const t=(n,ok,d='')=>R.push([ok?'OK ':'>>> KO',n,d].join(' | '));
// on intercepte le blob téléchargé pour lire le fichier ligne à ligne
await p.addInitScript(()=>{ window.__A=''; const o=URL.createObjectURL;
  URL.createObjectURL=function(bl){ bl.text().then(x=>{window.__A=x;}); return o.call(URL,bl); }; });
const lire=async()=>(await p.evaluate(()=>window.__A)).split('\r\n').filter(x=>x.length);
const exporter=async()=>{ await p.locator('.stp[data-go="5"]').click(); await p.waitForTimeout(200);
  await p.click('.js-download'); await p.waitForTimeout(400);
  const L=await lire(); await p.click('.js-modal-close'); await p.waitForTimeout(150); return L; };

await p.goto(PAGE);
await p.click('.js-login button[type=submit]');
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(300);
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(300);

const L0=await exporter();
t('fichier produit', L0.length>0, L0.length+' lignes');
t('251 caractères par ligne', L0.every(l=>l.length===251), [...new Set(L0.map(l=>l.length))].join('/'));
t('dates au format JJMMAA', L0.every(l=>/^\d{6}$/.test(l.slice(14,20))), L0[0].slice(14,20));
t('comptes cadrés sur 8 caractères', L0.every(l=>/^\d{8}$/.test(l.slice(1,9))), L0[0].slice(1,9));

// deux journaux : le relevé en banque, l'exception en OD
const bq=L0.filter(l=>l.slice(9,11)==='BQ'), od=L0.filter(l=>l.slice(9,11)==='OD');
t('relevé -> journal BQ, contrepartie 512',
  bq.length>0 && bq.every(l=>l.slice(55,63)==='51200000'), bq.length+' lignes');
t('hors relevé -> journal OD, contrepartie 108',
  od.length===1 && od.every(l=>l.slice(55,63)==='10800000'), od.length+' ligne');
// En trésorerie, pas de flux, pas d'écriture : une facture dont le règlement
// n'est ni en banque ni mentionné sur la pièce ne doit RIEN produire.
t('facture sans règlement identifié : aucune écriture',
  !L0.some(l=>/STORES/.test(l)),
  'STORES & VOLETS AZUR (1 240 €) absente du fichier');
t('sens : les crédits sont au crédit',
  L0.some(l=>l[41]==='C') && L0.some(l=>l[41]==='D'),
  'C='+L0.filter(l=>l[41]==='C').length+' D='+L0.filter(l=>l[41]==='D').length);

// trésorerie : l'OD est datée du jour du règlement porté par la pièce
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(200);
await p.locator('.js-wstabs .optab', {hasText:'hors relevé'}).click(); await p.waitForTimeout(250);
await p.locator('.oprow', {hasText:'PLOMBERIE'}).click(); await p.waitForTimeout(200);
await p.locator('.js-paie').fill('05/11/2026');
await p.locator('.js-paie').blur(); await p.waitForTimeout(250);
const L1=await exporter();
t('la date saisie fait naître l\'écriture',
  L1.filter(l=>l.slice(9,11)==='OD').length===2
  && L1.filter(l=>l.slice(9,11)==='OD').some(l=>l.slice(14,20)==='051126'),
  L1.filter(l=>l.slice(9,11)==='OD').map(l=>l.slice(14,20)).join(' '));

// une ventilation produit une ligne de plus
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(200);
await p.locator('.js-wstabs .optab').first().click(); await p.waitForTimeout(200);
await p.locator('.oprow', {hasText:'MENUISERIE DES CIMES'}).click(); await p.waitForTimeout(200);
await p.locator('.js-split').click(); await p.waitForTimeout(250);
const ins=p.locator('.split-l input[type=number]');
const tot=parseFloat(await ins.nth(0).inputValue());
await ins.nth(0).fill((tot*0.6).toFixed(2)); await ins.nth(1).fill((tot*0.4).toFixed(2));
await p.locator('.split-l select').nth(1).selectOption({index:1});
await p.click('.js-modal-ok'); await p.waitForTimeout(300);
const L2=await exporter();
t('la ventilation ajoute une ligne', L2.length===L1.length+1, L1.length+' -> '+L2.length);
const somme=L2.reduce((a,l)=>a+ +l.slice(43,55),0)/100;
const somme1=L1.reduce((a,l)=>a+ +l.slice(43,55),0)/100;
t('le total ne bouge pas', Math.abs(somme-somme1)<0.005, somme.toFixed(2)+' €');

// dossier sans banque : tout en OD 108
await p.click('.js-home'); await p.waitForTimeout(150);
await p.click('[data-name="LMNP_BERNARD_2025"]'); await p.waitForTimeout(450);
await p.locator('.js-modal-ok').click().catch(()=>{}); await p.waitForTimeout(200);
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(250);
const L3=await exporter();
t('sans banque : tout en OD 108',
  L3.length>0 && L3.every(l=>l.slice(9,11)==='OD' && l.slice(55,63)==='10800000'),
  L3.length+' lignes');
console.log(R.join('\n'));
console.log('\nERREURS JS: '+(errs.length?errs.join('\n'):'aucune'));
await b.close();
