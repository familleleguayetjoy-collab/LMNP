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

// 1. règles pilotent les onglets
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(250);
await p.click('.js-regles'); await p.waitForTimeout(200);
await p.fill('.js-seuil','5000'); await p.waitForTimeout(150);   // plus aucune ligne « montant »
await p.click('.js-modal-close'); await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(200);
const ong1=(await p.locator('.optab').allInnerTexts()).map(x=>x.replace(/\n/g,''));
t('seuil 5000 -> onglet Montant disparaît', !ong1.some(x=>x.startsWith('Montant')), ong1.join(' / '));
await p.locator('.stp[data-go="1"]').click(); await p.click('.js-regles'); await p.waitForTimeout(150);
await p.fill('.js-seuil','1500'); await p.waitForTimeout(150);
await p.locator('.rulecard').first().locator('.js-regle').uncheck(); await p.waitForTimeout(150);
await p.click('.js-modal-close'); await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(200);
const ong2=(await p.locator('.optab').allInnerTexts()).map(x=>x.replace(/\n/g,''));
t('règle Immobilisation décochée -> onglet disparaît', !ong2.some(x=>x.startsWith('Immob')), ong2.join(' / '));
await p.locator('.stp[data-go="1"]').click(); await p.click('.js-regles'); await p.waitForTimeout(150);
await p.locator('.rulecard').first().locator('.js-regle').check(); await p.waitForTimeout(150);
await p.click('.js-modal-close');

// 2. persistance après rechargement
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(200);
await p.locator('.js-imput').first().selectOption('615'); await p.waitForTimeout(150);
await p.reload(); await p.waitForTimeout(300);
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(400);
await p.locator('.js-modal-ok').click().catch(()=>{});   // écran de reprise éventuel
await p.waitForTimeout(200);
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(200);
t('imputation conservée après rechargement', (await p.locator('.js-imput').first().inputValue())==='615');

// 3. date de paiement saisissable
const nbDates = await p.locator('.js-datepaie').count();
t('champ date de paiement présent', nbDates>0, nbDates+' champ(s)');

// 4. deux onglets de justificatifs + mail en deux sections
await p.locator('.stp[data-go="3"]').click(); await p.waitForTimeout(200);
const rectabs=(await p.locator('.js-rectabs .optab').allInnerTexts()).map(x=>x.replace(/\n/g,''));
t('deux onglets de réclamation', rectabs.length===2, rectabs.join(' / '));
await p.click('.js-recvalider'); await p.waitForTimeout(150);
await p.click('.js-recvalider'); await p.waitForTimeout(200);
t('étape 4 atteinte', (await p.getAttribute('.lmnp','data-step'))==='4');
const secs=await p.locator('.mailsec').count();
t('mail en deux sections', secs===2, (await p.locator('.mailsec p b').allInnerTexts()).join(' | '));

// 5. déconnexion
t('bouton déconnexion présent', (await p.locator('.js-logout').count())===1);
// 6. export : ventilation
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(200);
await p.locator('.js-split').first().click(); await p.waitForTimeout(200);
const ins=p.locator('.split-l input[type=number]');
const total=parseFloat(await ins.nth(0).inputValue());
await ins.nth(0).fill((total*0.6).toFixed(2)); await ins.nth(1).fill((total*0.4).toFixed(2));
await p.locator('.split-l select').nth(1).selectOption({index:1});
await p.click('.js-modal-ok'); await p.waitForTimeout(250);
const nbL = await p.evaluate(()=>{
  const dl=[...document.querySelectorAll('a')].length; return document.querySelectorAll('.ventil').length;});
t('ventilation enregistrée', nbL===1);
console.log(R.join('\n'));
console.log('\nERREURS JS: '+(errs.length?errs.join('\n'):'aucune'));
await b.close();
