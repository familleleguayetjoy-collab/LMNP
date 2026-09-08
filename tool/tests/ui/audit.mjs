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
const ong=(await p.locator('.accong').allInnerTexts()).map(x=>x.replace(/\n/g,''));
t('trois onglets : nouveaux, à jour, tous', ong.length===3, ong.join(' | '));
const nNeuf=await p.locator('.dosrow').count();
t('« Nouveaux éléments » ne liste que les dossiers à traiter',
  nNeuf>0 && (await p.locator('.pneuf').count())===nNeuf
  && (await p.locator('.pill.maj').count())===0, nNeuf+' dossiers');
t('le nombre de nouvelles pièces est en rouge', await p.evaluate(()=>{
  const m=/(\d+), (\d+), (\d+)/.exec(getComputedStyle(document.querySelector('.pneuf')).color);
  return +m[1] > +m[2]+40 && +m[1] > +m[3]+40;}),
  await p.evaluate(()=>getComputedStyle(document.querySelector('.pneuf')).color));
await p.locator('.accong').nth(1).click(); await p.waitForTimeout(200);
const nJour=await p.locator('.dosrow').count();
t('« À jour » : nom + date de mise à jour, rien d\'autre',
  nJour>0 && (await p.locator('.pill.maj').count())===nJour
  && (await p.locator('.pneuf').count())===0,
  nJour+' dossiers · '+await p.locator('.pill.maj').first().innerText());
await p.fill('.js-rech','azur'); await p.waitForTimeout(250);
t('la recherche filtre', (await p.locator('.dosrow').count())===1,
  await p.locator('.dosrow .dnom').innerText());
await p.fill('.js-rech',''); await p.selectOption('.js-filtretype','sci'); await p.waitForTimeout(250);
t('le filtre par type filtre', (await p.locator('.dosrow').count())===2);
await p.selectOption('.js-filtretype',''); await p.locator('.accong').nth(0).click();
await p.waitForTimeout(200);
// création réelle d'un dossier, avec son exercice
await p.click('.js-newdossier'); await p.waitForTimeout(200);
t('Nouveau dossier : le bouton attend une saisie valable',
  await p.locator('.js-modal-ok').isDisabled());
await p.fill('.js-nd-nom','SCI_TEST_2027');
await p.fill('.js-nd-du','01072026'); await p.fill('.js-nd-au','30062027');
await p.waitForTimeout(200);
t('Nouveau dossier : les dates se mettent en forme',
  (await p.locator('.js-nd-du').inputValue())==='01/07/2026'
  && !(await p.locator('.js-modal-ok').isDisabled()));
await p.click('.js-modal-ok'); await p.waitForTimeout(500);
t('Nouveau dossier : créé, ouvert, exercice repris',
  (await p.getAttribute('.lmnp','data-step'))==='1'
  && (await p.locator('.step[data-s="1"] .js-dossier').innerText()).includes('SCI_TEST_2027')
  && (await p.locator('.js-du').innerText())==='01/07/2026'
  && (await p.locator('.js-au').innerText())==='30/06/2027');
await p.click('.js-home'); await p.waitForTimeout(250);
await p.locator('.accong').nth(2).click(); await p.waitForTimeout(200);
t('Nouveau dossier : présent dans la liste',
  (await p.locator('[data-name="SCI_TEST_2027"]').count())===1);
await p.locator('.accong').nth(0).click(); await p.waitForTimeout(200);

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
const carteM=p.locator('.rulecard').filter({hasText:'Dépense non immobilisable'});
t('règles : le paramétrage complet, trois niveaux par règle',
  nCartes>=30 && (await p.locator('.rulecard').first().locator('.niv').count())===3
  && (await p.locator('.rulefam').count())===6,
  nCartes+' règles en '+(await p.locator('.rulefam').count())+' familles');
t('règles : celles qui attendent la donnée sont signalées',
  (await p.locator('.rulecard.dormante').count())>0
  && /branchées aujourd/.test(await p.locator('.js-rulecount').innerText()),
  (await p.locator('.js-rulecount').innerText()).split('—')[1]);
await p.locator('.rulecard').first().locator('.niv[data-n="0"]').click(); await p.waitForTimeout(120);
const pied=await p.locator('.js-rulecount').innerText();
t('règles : le décompte suit les niveaux', /automatique/.test(pied), pied.replace(/\n/g,' '));
await carteM.locator('.js-seuil').fill('2500'); await p.waitForTimeout(120);
await p.click('.js-modal-close');
await p.click('.js-regles'); await p.waitForTimeout(200);
t('règles : réglages conservés',
  (await p.locator('.rulecard').filter({hasText:'Dépense non immobilisable'}).locator('.js-seuil').inputValue())==='2500'
  && (await p.locator('.rulecard').first().locator('.niv.on').getAttribute('data-n'))==='0');
await p.locator('.rulecard').first().locator('.niv[data-n="2"]').click(); await p.waitForTimeout(120);
await p.click('.js-modal-close');
t('bouton historique masqué au 1er import', !(await p.locator('.js-dupbtn').isVisible()));

// ---- 4. ÉTAPE 2 : LE POSTE DE TRAVAIL ----
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(300);
const wtabs=(await p.locator('.js-wstabs .optab').allInnerTexts()).map(x=>x.replace(/\n/g,''));
t('quatre onglets de tri', wtabs.length===4, wtabs.join(' / '));
t('le relevé est listé', (await p.locator('.oprow').count())>10,
  (await p.locator('.oprow').count())+' lignes');
t('montants neutres, jamais rouges ni verts',
  await p.evaluate(()=>[...document.querySelectorAll('.oprow .amt')].every(e=>{
    const m=/(\d+), (\d+), (\d+)/.exec(getComputedStyle(e).color);
    if(!m)return false;
    const [r,g,b]=[+m[1],+m[2],+m[3]];
    return Math.max(r,g,b)-Math.min(r,g,b) < 20;   // gris : aucune dominante
  })),
  await p.evaluate(()=>[...new Set([...document.querySelectorAll('.oprow .amt')]
    .map(e=>getComputedStyle(e).color))].join(' ')));
t('un seul statut par ligne',
  await p.evaluate(()=>[...document.querySelectorAll('.oprow')]
    .every(r=>r.querySelectorAll('.chip').length===1)));
t('aucune cellule ne passe à la ligne',
  await p.evaluate(()=>[...document.querySelectorAll('.oprow td')]
    .every(e=>e.clientHeight<46)),
  await p.evaluate(()=>[...new Set([...document.querySelectorAll('.oprow td')]
    .map(e=>e.clientHeight))].join('/')+' px'));
// en-tête figée : elle doit rester au même endroit quand la liste défile
await p.evaluate(()=>{document.querySelector('.wleft .tblwrap').scrollTop=250;});
await p.waitForTimeout(200);
t('en-tête de colonnes figée au défilement', await p.evaluate(()=>{
  const w=document.querySelector('.wleft .tblwrap').getBoundingClientRect();
  const h=document.querySelector('.tbl.ops th').getBoundingClientRect();
  return Math.abs(h.top - w.top) < 2 && getComputedStyle(document.querySelector('.tbl.ops th')).backgroundImage!=='none';
}), 'défilement de 250 px');
await p.evaluate(()=>{document.querySelector('.wleft .tblwrap').scrollTop=0;});
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
t('onglet « À traiter » vidé',
  parseInt((await p.locator('.js-wstabs .optab').nth(1).innerText()).replace(/\D/g,''),10)===0,
  (await p.locator('.js-wstabs .optab').allInnerTexts()).map(x=>x.replace(/\n/g,'')).join(' / '));
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
