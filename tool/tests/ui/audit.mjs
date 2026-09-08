import { chromium } from 'playwright-core';
// Chemin du navigateur et de la page : surchargeables sans toucher au test.
const EXE = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PAGE = process.env.SAISIO || 'file://' + process.cwd().replace(/\/tool\/tests\/ui$/, '') + '/index.html';
const b = await chromium.launch({ executablePath: EXE });
const p = await b.newPage({viewport:{width:1440,height:900}});
const errs=[]; p.on('pageerror',e=>errs.push('JS: '+e.message));
p.on('console',m=>{if(m.type()==='error'&&!/ERR_CONNECTION/.test(m.text()))errs.push('CONSOLE: '+m.text());});
const R=[]; const t=(n,ok,d='')=>R.push([ok?'OK ':'KO ',n,d].join(' | '));

await p.goto(PAGE);

// ---- 1. CONNEXION ----
t('connexion affichée au démarrage', await p.locator('.js-auth').isVisible());
await p.fill('.js-email','paul@s2a-audit.fr'); await p.fill('.js-pwd','x');
await p.click('.js-login button[type=submit]'); await p.waitForTimeout(200);
t('connexion masquée après soumission', !(await p.locator('.js-auth').isVisible()));
const sess = await p.evaluate(()=>localStorage.getItem('saisio_session_v1'));
t('session mémorisée', !!sess && sess.includes('paul@s2a-audit.fr'));
await p.reload(); await p.waitForTimeout(250);
t('session survit au rechargement', !(await p.locator('.js-auth').isVisible()));

// ---- 2. ACCUEIL ----
t('barre d\'étapes masquée sur l\'accueil', !(await p.locator('.stepper').isVisible()));
const g=await p.locator('.dgroup.g-todo .dcard').count(), d2=await p.locator('.dgroup.g-done .dcard').count();
t('colonnes 3 + 4 dossiers', g===3&&d2===4, `gauche=${g} droite=${d2}`);
const pastilles=await p.locator('.dgroup.g-todo .st.neuf').allInnerTexts();
t('pastilles = nombre de nouvelles pièces', pastilles.every(x=>/\d/.test(x)), pastilles.join(' '));
await p.click('.js-newdossier'); await p.waitForTimeout(150);
t('bouton Nouveau dossier ouvre une fenêtre', await p.locator('.js-modal.on').isVisible());
await p.click('.js-modal-close');

// ---- 3. ÉTAPE 1 ----
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(300);
t('ouverture du dossier -> étape 1', (await p.getAttribute('.lmnp','data-step'))==='1');
t('nom du dossier propagé', (await p.locator('.step[data-s="1"] .js-dossier').innerText()).includes('DUPONT'));
t('barre d\'étapes visible', await p.locator('.stepper').isVisible());
// TVA
await p.click('.js-tva[data-v="oui"]'); await p.waitForTimeout(80);
const tvaOui=await p.getAttribute('.lmnp','data-tva');
await p.click('.js-tva[data-v="non"]'); await p.waitForTimeout(80);
t('bascule TVA fonctionne', tvaOui==='oui' && (await p.getAttribute('.lmnp','data-tva'))==='non');
// Banque
await p.click('.js-bq[data-v="non"]'); await p.waitForTimeout(80);
const bqNon=await p.getAttribute('.lmnp','data-banque');
await p.click('.js-bq[data-v="oui"]'); await p.waitForTimeout(80);
t('bascule Banque fonctionne', bqNon==='non');
// Type
await p.selectOption('.js-type','sci'); await p.waitForTimeout(80);
t('sélecteur Type opérant', (await p.locator('.js-type').inputValue())==='sci');
await p.selectOption('.js-type','lmnp');
// Import banque
await p.setInputFiles('.js-bqfile',{name:'releve_CA.txt',mimeType:'text/plain',buffer:Buffer.from('M...\r\n')});
await p.waitForTimeout(150);
t('import banque : fichier accepté', await p.locator('.js-bqok').isVisible(),
  await p.locator('.js-bqnom').innerText());
// Règles
await p.click('.js-regles'); await p.waitForTimeout(200);
const nCartes=await p.locator('.rulecard').count();
await p.locator('.rulecard .js-regle').first().uncheck(); await p.waitForTimeout(80);
const pied=await p.locator('.js-rulecount').innerText();
await p.locator('.rulecard').filter({hasText:'Montant supérieur'}).locator('.js-seuil').fill('2500'); await p.waitForTimeout(80);
t('règles : cartes + décompte + seuil', nCartes===8 && pied.includes('7'), `${nCartes} cartes, "${pied}"`);
await p.click('.js-modal-close');
await p.click('.js-regles'); await p.waitForTimeout(150);
t('règles : réglages conservés', (await p.locator('.rulecard').filter({hasText:'Montant supérieur'}).locator('.js-seuil').inputValue())==='2500'
   && !(await p.locator('.rulecard .js-regle').first().isChecked()));
await p.locator('.rulecard .js-regle').first().check();
await p.click('.js-modal-close');
t('bouton historique masqué au 1er import', !(await p.locator('.js-dupbtn').isVisible()));

// ---- 4. ÉTAPE 2 : LE POSTE DE TRAVAIL ----
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(300);
const wtabs=(await p.locator('.js-wstabs .optab').allInnerTexts()).map(x=>x.replace(/\n/g,''));
t('quatre onglets de tri', wtabs.length===4, wtabs.join(' / '));
t('le relevé est listé', (await p.locator('.oprow').count())>10,
  (await p.locator('.oprow').count())+' lignes');
t('débits en rouge, crédits en vert',
  (await p.locator('.oprow .amt.db').count())>0 && (await p.locator('.oprow .amt.cr').count())>0);
t('une ligne est sélectionnée d\'office', (await p.locator('.oprow.on').count())===1,
  await p.locator('.oprow.on .lib').innerText());
t('la pièce est affichée à droite', (await p.locator('.facsvg, .nopiece').count())>0);
t('la décision est à droite', (await p.locator('.js-wform .js-imput').count())===1);
t('deux boutons de sortie', (await p.locator('.js-wpied button').count())===2,
  (await p.locator('.js-wpied').innerText()).replace(/\n/g,' '));
// on traite tout le dossier au clavier
let tours=0;
while(parseInt((await p.locator('.js-wstabs .optab').nth(1).innerText()).replace(/\D/g,''),10)>0 && tours<25){
  await p.keyboard.press('Enter'); await p.waitForTimeout(120); tours++;
}
t('le dossier se traite entièrement', tours<25 && tours>0, tours+' validations');
t('compteur à zéro', (await p.locator('.js-wcount').innerText()).includes('Tout est traité'),
  (await p.locator('.js-wcount').innerText()).replace(/\n/g,' '));
await p.click('.js-valider'); await p.waitForTimeout(250);
t('passage aux justificatifs', (await p.getAttribute('.lmnp','data-step'))==='3');

// ---- 5. ÉTAPE 3 / 4 ----
const nJust=await p.locator('.ritem').count();
const nBadge=await p.locator('.badge-h .n').first().innerText();
await p.locator('.ritem').first().click(); await p.waitForTimeout(120);
const apres=await p.locator('.ritem[aria-checked="true"]').count();
t('justificatifs cochables', nJust>0 && apres===nJust-1, `${nJust} pièces, badge ${nBadge}`);
await p.locator('.ritem').first().click();
while(await p.getAttribute('.lmnp','data-step')==='3'){
  await p.click('.js-recvalider'); await p.waitForTimeout(180); }
const mail=await p.locator('.mail').innerText();
t('mail : destinataire + objet + liste', mail.includes('@') && /justificatif/i.test(mail),
  mail.split('\n').slice(0,2).join(' '));
const nLignesMail=await p.locator('.mailsec li').count();
const nAnnonce=parseInt(await p.locator('.js-mail-n').first().innerText(),10);
t('mail synchronisé avec les cases', nLignesMail===nAnnonce && nLignesMail>0,
  `${nLignesMail} lignes, objet annonce ${nAnnonce}`);

// ---- 6. ÉTAPE 5 ----
await p.click('.step[data-s="4"] .js-next'); await p.waitForTimeout(200);
t('étape 5 atteinte', (await p.getAttribute('.lmnp','data-step'))==='5');
t('carte Excel visible avec banque', await p.locator('.js-file-xlsx').isVisible());
t('titre ASCII adapté', (await p.locator('.js-ascii-title').innerText()).includes('OD'));
await p.click('.js-download'); await p.waitForTimeout(250);
const exp=await p.locator('.js-modal-content').innerText();
t('export : fenêtre + noms horodatés', exp.includes('exporté') && /_\d{8}-\d{4}/.test(exp),
  (exp.match(/[A-Z_0-9]+_\d{8}-\d{4}\.\w+/g)||[]).join(' '));
await p.click('.js-modal-close');

// ---- 7. ANTI-DOUBLON (2e passage) ----
await p.click('.js-home'); await p.waitForTimeout(150);
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(450);
if(await p.locator('.js-modal.on').count()){          // écran de reprise
  t('écran de reprise au 2e passage', true,
    (await p.locator('.js-modal-content h3').innerText()));
  await p.locator('.js-modal-ok').click(); await p.waitForTimeout(250); }
t('2e ouverture : bouton historique visible', await p.locator('.js-dupbtn').isVisible());
await p.click('.js-dupbtn'); await p.waitForTimeout(150);
t('historique : message anti-doublon', (await p.locator('.js-modal-content').innerText()).includes('déjà été importé'));
await p.click('.js-modal-close');

// ---- 8. DÉFILEMENT ----
for(const s of ['0','1','2','3','4','5']){
  if(s==='0')await p.click('.js-home'); else await p.locator(`.stp[data-go="${s}"]`).click().catch(()=>{});
  await p.waitForTimeout(120);
  const sc=await p.evaluate(()=>document.documentElement.scrollHeight>window.innerHeight+2);
  if(s!=='0') t(`étape ${s} tient dans l'écran`, !sc);
}
console.log(R.join('\n'));
console.log('\nERREURS JS: '+(errs.length?errs.join('\n'):'aucune'));
await b.close();
