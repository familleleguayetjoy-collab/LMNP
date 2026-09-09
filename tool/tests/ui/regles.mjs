import { chromium } from 'playwright-core';
// Les règles de contrôle pilotent réellement ce qui remonte à l'humain.
const EXE = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PAGE = process.env.SAISIO || 'file://' + process.cwd().replace(/\/tool\/tests\/ui$/, '') + '/index.html';
const b = await chromium.launch({ executablePath: EXE });
const p = await b.newPage({viewport:{width:1440,height:900}});
const errs=[]; p.on('pageerror',e=>errs.push('JS: '+e.message));
const R=[]; const t=(n,ok,d='')=>R.push([ok?'OK ':'>>> KO',n,d].join(' | '));
const carte=(txt)=>p.locator('.rulecard').filter({hasText:txt});
const statuts=async()=>{ await p.locator('.js-wstabs .optab').first().click(); await p.waitForTimeout(150);
  return (await p.locator('.oprow .chip').allInnerTexts()).map(x=>x.trim()); };
const ouvrir=async()=>{ await p.locator('.stp[data-go="1"]').click(); await p.waitForTimeout(150);
  await p.click('.js-regles'); await p.waitForTimeout(200); };
const niveau=async(regle,n)=>{ await carte(regle).locator('.niv[data-n="'+n+'"]').click();
  await p.waitForTimeout(150); };
const fermer=async()=>{ await p.click('.js-modal-close'); await p.waitForTimeout(150);
  await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(250); };

await p.goto(PAGE);
await p.click('.js-login button[type=submit]');
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(300);
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(300);

const base=await statuts();
t('les sept statuts sont produits',
  ['Sans pièce','Immobilisé','Acompte','Multi-règl.','Montant élevé',
   'Nouveau','À qualifier'].every(s=>base.includes(s)),
  [...new Set(base)].join(' / '));

// seuil de montant : au-delà du plus gros mouvement, plus aucun « montant élevé »
await ouvrir();
await carte('Dépense non immobilisable').locator('.js-seuil').fill('9000'); await p.waitForTimeout(150);
await fermer();
t('seuil relevé -> plus de « Montant élevé »', !(await statuts()).includes('Montant élevé'));
await ouvrir(); await carte('Dépense non immobilisable').locator('.js-seuil').fill('1500');
await p.waitForTimeout(150); await fermer();
t('seuil rétabli -> le statut revient', (await statuts()).includes('Montant élevé'));

// seuil de justificatif : au-delà, plus rien à réclamer
await ouvrir();
await carte('sans facture disponible').locator('.js-seuil').fill('9000'); await p.waitForTimeout(150);
await fermer();
t('seuil de justificatif relevé -> plus de « Sans pièce »',
  !(await statuts()).includes('Sans pièce'));
await ouvrir(); await carte('sans facture disponible').locator('.js-seuil').fill('150');
await p.waitForTimeout(150); await fermer();

// décocher une règle la retire complètement
// les réglages survivent au rechargement
await ouvrir(); await carte('Dépense non immobilisable').locator('.js-seuil').fill('2200');
await p.waitForTimeout(200); await p.click('.js-modal-close');
await p.reload(); await p.waitForTimeout(400);
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(500);
await p.locator('.js-modal-ok').click().catch(()=>{}); await p.waitForTimeout(200);
await p.click('.js-regles'); await p.waitForTimeout(250);
t('réglages conservés après rechargement',
  (await carte('Dépense non immobilisable').locator('.js-seuil').inputValue())==='2200');
await p.click('.js-modal-close');

// chaque règle restante pilote bien un statut
for(const [regle,statut] of [['Acompte ou situation de travaux','Acompte'],
                             ['Paiement fractionné','Multi-règl.'],
                             ['jamais utilisé auparavant','Nouveau'],
                             ['Confiance de l','À qualifier'],
                             ['Immobilisation détectée','Immobilisé'],
                             ['sans facture disponible','Sans pièce']]){
  await ouvrir(); await niveau(regle,0); await fermer();
  const sans=!(await statuts()).includes(statut);
  await ouvrir(); await niveau(regle,1); await fermer();
  t('règle « '+regle+' » pilote « '+statut+' »',
    sans && (await statuts()).includes(statut));
}
// la règle « sans règlement en banque » gouverne l'onglet des factures hors relevé
await ouvrir(); await niveau('Règlement sans facture',0);
await p.waitForTimeout(150); await fermer();
const sansOnglet=!(await p.locator('.js-wstabs .optab').allInnerTexts()).some(x=>/Hors relev/i.test(x));
await ouvrir(); await niveau('Règlement sans facture',1);
await p.waitForTimeout(150); await fermer();
t('la règle « sans règlement » gouverne l\'onglet hors relevé',
  sansOnglet && (await p.locator('.js-wstabs .optab').allInnerTexts()).some(x=>/Hors relev/i.test(x)));

// le niveau « validation obligatoire » interdit le traitement en série
// SYNDIC AZUR a trois lignes : le bouton de série DOIT exister au niveau 1
await ouvrir(); await niveau('sans facture disponible',1); await fermer();
await p.locator('.oprow', {hasText:'SYNDIC AZUR APPEL T1'}).click(); await p.waitForTimeout(250);
const serieAvant=await p.locator('.js-serie').count();
await ouvrir(); await niveau('sans facture disponible',2); await fermer();
await p.locator('.oprow', {hasText:'SYNDIC AZUR APPEL T1'}).click(); await p.waitForTimeout(250);
const serieApres=await p.locator('.js-serie').count();
t('validation obligatoire : pas de traitement en série',
  serieAvant===1 && serieApres===0,
  'à contrôler -> '+serieAvant+' bouton, obligatoire -> '+serieApres);
await ouvrir(); await niveau('sans facture disponible',1); await fermer();

// le compteur du pied de la fenêtre
await p.locator('.stp[data-go="1"]').click(); await p.waitForTimeout(150);
await p.click('.js-regles'); await p.waitForTimeout(200);
const n=await p.locator('.rulecard').count();
t('le décompte suit le paramétrage',
  n>=30 && /à contrôler/.test(await p.locator('.js-rulecount').innerText()),
  (await p.locator('.js-rulecount').innerText()).replace(/\n/g,' '));
console.log(R.join('\n'));
console.log('\nERREURS JS: '+(errs.length?errs.join('\n'):'aucune'));
await b.close();
