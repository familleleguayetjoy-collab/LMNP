import { chromium } from 'playwright-core';
// Le poste de travail (étape 2) : le relevé à gauche, la décision à droite.
const EXE = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PAGE = process.env.SAISIO || 'file://' + process.cwd().replace(/\/tool\/tests\/ui$/, '') + '/index.html';
const b = await chromium.launch({ executablePath: EXE });
const p = await b.newPage({viewport:{width:1440,height:900}});
const errs=[]; p.on('pageerror',e=>errs.push('JS: '+e.message));
const R=[]; const t=(n,ok,d='')=>R.push([ok?'OK ':'>>> KO',n,d].join(' | '));
const nTodo=async()=>parseInt((await p.locator('.js-wstabs .optab').nth(1).innerText()).replace(/\D/g,''),10);

await p.goto(PAGE);
await p.click('.js-login button[type=submit]');
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(300);
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(300);

// ---- tri ----
await p.locator('.js-sort[data-k="lib"]').click(); await p.waitForTimeout(150);
const libs=await p.locator('.oprow .lib').allInnerTexts();
t('tri par libellé', libs[0].localeCompare(libs[1],'fr')<=0, libs.slice(0,3).join(' , '));
await p.locator('.js-sort[data-k="m"]').click(); await p.waitForTimeout(150);
const mts=(await p.locator('.oprow .amt').allInnerTexts()).map(x=>parseFloat(x.replace(/[^\d,]/g,'').replace(',','.')));
t('tri par montant croissant', mts[0]<=mts[mts.length-1], mts[0]+' -> '+mts[mts.length-1]);
await p.locator('.js-sort[data-k="m"]').click(); await p.waitForTimeout(150);
const mts2=(await p.locator('.oprow .amt').allInnerTexts()).map(x=>parseFloat(x.replace(/[^\d,]/g,'').replace(',','.')));
t('second clic : tri inversé', mts2[0]>=mts2[mts2.length-1], mts2[0]+' -> '+mts2[mts2.length-1]);
await p.locator('.js-sort[data-k="dt"]').click(); await p.waitForTimeout(150);

// ---- onglets ----
const wt=(await p.locator('.js-wstabs .optab').allInnerTexts()).map(x=>x.replace(/\n/g,''));
t('quatre onglets', wt.length===4, wt.join(' / '));
await p.locator('.js-wstabs .optab').nth(1).click(); await p.waitForTimeout(200);
t('« À traiter » ne montre que les lignes à statut',
  (await p.locator('.oprow .chip.auto').count())===0, (await p.locator('.oprow').count())+' lignes');
await p.locator('.js-wstabs .optab').nth(0).click(); await p.waitForTimeout(200);

// ---- imputation en série ----
await p.locator('.oprow', {hasText:'SYNDIC AZUR APPEL T1'}).click(); await p.waitForTimeout(200);
const se=p.locator('.js-serie');
t('imputation en série proposée', await se.count()===1, await se.innerText().catch(()=>'absent'));
t('absence de pièce signalée', (await p.locator('.nopiece').count())===1);
await p.click('.js-reclamer'); await p.waitForTimeout(200);
t('« demander la pièce » enregistré',
  (await p.locator('.js-reclamer').innerText()).includes('Sera demandée'));
const av=await nTodo(); await se.click(); await p.waitForTimeout(250);
t('la fenêtre confirme la série',
  (await p.locator('.js-modal-content').innerText()).includes('SYNDIC'));
await p.click('.js-modal-close'); await p.waitForTimeout(150);
t('les 3 lignes du fournisseur sortent d\'un coup', (await nTodo())===av-3, av+' -> '+await nTodo());

// ---- valider / laisser en 471 ----
await p.locator('.js-wstabs .optab').nth(1).click(); await p.waitForTimeout(200);
const s1=await p.locator('.oprow.on .lib').innerText();
await p.click('.js-okimput'); await p.waitForTimeout(250);
t('« Valider et suivant » enchaîne', (await p.locator('.oprow.on .lib').innerText())!==s1,
  s1+' -> '+await p.locator('.oprow.on .lib').innerText());
await p.click('.js-attente'); await p.waitForTimeout(250);
await p.locator('.js-wstabs .optab').nth(0).click(); await p.waitForTimeout(200);
t('471 tracé, pas oublié', (await p.locator('.chip.att').count())>0);

// ---- les trois sorties, dans un seul bloc ----
await p.locator('.js-wstabs .optab').nth(0).click(); await p.waitForTimeout(200);
await p.locator('.oprow', {hasText:'VIREMENT LOYER MARS'}).click(); await p.waitForTimeout(250);
t('les trois sorties dans le même bloc', (await p.locator('.js-wpied .wb').count())===3,
  (await p.locator('.js-wpied').innerText()).replace(/\n+/g,' | '));
t('valider en vert, attente en ambre, série en gris', await p.evaluate(()=>{
  const c=n=>getComputedStyle(document.querySelector('.js-wpied .wb.'+n)).backgroundColor;
  return c('ok')==='rgb(27, 127, 75)' && c('att')==='rgb(252, 241, 227)'
      && c('ser')==='rgb(237, 239, 242)';}));

// ---- clavier ----
const k0=await p.locator('.oprow.on .lib').innerText();
await p.keyboard.press('ArrowDown'); await p.waitForTimeout(200);
const k1=await p.locator('.oprow.on .lib').innerText();
t('flèche bas', k0!==k1, k0+' -> '+k1);
await p.keyboard.press('ArrowUp'); await p.waitForTimeout(200);
t('flèche haut', (await p.locator('.oprow.on .lib').innerText())===k0);
await p.keyboard.press('Enter'); await p.waitForTimeout(250);
t('Entrée valide', (await p.locator('.oprow.on .lib').innerText())!==k0);

// ---- factures réglées hors relevé ----
await p.locator('.js-wstabs .optab', {hasText:'Hors relevé'}).click(); await p.waitForTimeout(250);
t('trois factures hors relevé', (await p.locator('.oprow').count())===3,
  (await p.locator('.oprow .chip').allInnerTexts()).map(x=>x.trim()).join(' / '));
// trois états bien distincts : datée, acquittée sans date, jamais réglée
await p.locator('.oprow', {hasText:'STORES'}).click(); await p.waitForTimeout(250);
t('facture sans aucun règlement : aucune écriture annoncée',
  /Aucune écriture ne sera produite/.test(await p.locator('.odnote').innerText()));
t('et on peut interroger le client',
  (await p.locator('.js-demdate').innerText()).includes('réglée'));
await p.locator('.oprow', {hasText:'SYNDIC AZUR APPEL T3'}).click(); await p.waitForTimeout(200);
t('OD 108 annoncée avec sa date', (await p.locator('.odnote').innerText()).includes('12/07/2026'),
  (await p.locator('.odnote').innerText()));
t('date de règlement saisissable', (await p.locator('.js-paie').count())===1);
await p.locator('.oprow', {hasText:'PLOMBERIE'}).click(); await p.waitForTimeout(200);
t('sans date : impossible de dater l\'OD', (await p.locator('.odnote.manque').count())===1);
await p.click('.js-demdate'); await p.waitForTimeout(250);
t('date demandée au client', (await p.locator('.js-demdate').innerText()).includes('demandée'));
await p.locator('.stp[data-go="3"]').click(); await p.waitForTimeout(250);
await p.locator('.js-rectabs .optab').nth(1).click(); await p.waitForTimeout(200);
t('la demande arrive dans « Règlement à justifier »',
  (await p.locator('.js-reclam .rlib').allInnerTexts()).some(x=>/PLOMBERIE/i.test(x)),
  (await p.locator('.js-reclam .rlib').allInnerTexts()).join(' | '));

// ---- persistance ----
await p.reload(); await p.waitForTimeout(400);
await p.click('[data-name="LMNP_DUPONT_2026"]'); await p.waitForTimeout(500);
await p.locator('.js-modal-ok').click().catch(()=>{}); await p.waitForTimeout(200);
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(300);
t('validations conservées après rechargement', (await p.locator('.chip.ok').count())>0,
  (await p.locator('.chip.ok').count())+' validée(s)');
t('471 conservé', (await p.locator('.chip.att').count())>0);
t('on rouvre sur « Tout »', (await p.locator('.js-wstabs .optab').first().getAttribute('class')).includes('on'));

// ---- la vraie pièce : une image déposée remplace l'aperçu ----
await p.locator('.js-wstabs .optab').nth(0).click(); await p.waitForTimeout(200);
await p.locator('.oprow', {hasText:'LA POSTE'}).click(); await p.waitForTimeout(250);
t('aperçu schématique par défaut', (await p.locator('.facsvg.ticket').count())===1);
const png = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64');
await p.setInputFiles('.js-photo', {name:'ticket.png', mimeType:'image/png', buffer:png});
await p.waitForTimeout(300);
t('la photo déposée remplace l\'aperçu',
  (await p.locator('.facimg').count())===1 && (await p.locator('.facsvg').count())===0,
  (await p.locator('.facimg').getAttribute('src')||'').slice(0,22));
t('on peut la remplacer', (await p.locator('.depose').innerText()).includes('Remplacer'));
// un PDF n'est pas une image : il lui faut un lecteur
const pdf = Buffer.from('%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>','latin1');
await p.setInputFiles('.js-photo', {name:'facture.pdf', mimeType:'application/pdf', buffer:pdf});
await p.waitForTimeout(400);
t('un PDF déposé s\'affiche dans un lecteur, pas dans une balise image',
  (await p.locator('.facpdf').count())===1 && (await p.locator('.facimg').count())===0);
await p.setInputFiles('.js-photo', {name:'ticket.png', mimeType:'image/png', buffer:png});
await p.waitForTimeout(300);
t('retour à une image après un PDF', (await p.locator('.facimg').count())===1);

// ---- le rail : cinq icônes qui se partagent la hauteur ----
t('les cinq étapes occupent toute la hauteur du rail', await p.evaluate(()=>{
  const st=[...document.querySelectorAll('.stp')];
  const somme=st.reduce((a,e)=>a+e.getBoundingClientRect().height,0);
  const rail=document.querySelector('.rail').getBoundingClientRect().height;
  return st.length===5 && somme > rail*0.6;}),
  await p.evaluate(()=>[...document.querySelectorAll('.stp')]
    .map(e=>Math.round(e.getBoundingClientRect().height)).join('+')));

// ---- les onglets couvrent la largeur de la liste ----
t('onglets de la gauche de Date à la droite de Statut', await p.evaluate(()=>{
  const t=document.querySelector('.js-wstabs').getBoundingClientRect();
  const l=document.querySelector('.wleft').getBoundingClientRect();
  return Math.abs(t.left-l.left)<2 && Math.abs(t.right-l.right)<3;}));

// ---- les champs de la décision s'alignent, quel que soit le libellé ----
// La propriété qui compte : deux champs CÔTE À CÔTE partagent le même bas,
// même quand l'un des deux intitulés passe à la ligne.
const alignes = async () => await p.evaluate(()=>{
  // On reconstitue les RANGÉES de la grille (2 colonnes ; un bloc « w2 » en
  // occupe deux) plutôt que de deviner par la distance : deux champs de la
  // même rangée doivent avoir exactement le même bas.
  const items=[...document.querySelector('.wgrid').children];
  const rangees=[]; let cour=[], col=0;
  items.forEach(function(el){
    const large=el.classList.contains('w2') ? 2 : 1;
    if(col+large>2){ rangees.push(cour); cour=[]; col=0; }
    cour.push(el); col+=large;
    if(col>=2){ rangees.push(cour); cour=[]; col=0; }
  });
  if(cour.length) rangees.push(cour);
  let n=0;
  for(const r of rangees){
    const bas=r.map(function(el){
      const i=el.querySelector('input'); return i ? Math.round(i.getBoundingClientRect().bottom) : null;
    }).filter(function(x){return x!==null;});
    n+=bas.length;
    if(bas.length>1 && Math.max.apply(null,bas)-Math.min.apply(null,bas) > 1) return false;
  }
  return n;
});
await p.locator('.js-wstabs .optab').nth(0).click(); await p.waitForTimeout(200);
await p.locator('.oprow').first().click(); await p.waitForTimeout(250);
t('champs alignés — ligne du relevé', (await alignes())>=3, (await alignes())+' champs');
await p.locator('.stp[data-go="1"]').click(); await p.waitForTimeout(150);
await p.click('.js-tva[data-v="oui"]');            // ajoute la colonne « dont TVA »
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(300);
await p.locator('.oprow').first().click(); await p.waitForTimeout(250);
t('champs alignés — avec la colonne TVA', (await alignes())>=4, (await alignes())+' champs');
await p.locator('.js-wstabs .optab',{hasText:'Hors relevé'}).click(); await p.waitForTimeout(250);
await p.locator('.oprow').first().click(); await p.waitForTimeout(250);
t('champs alignés — facture hors relevé', (await alignes())>=4, (await alignes())+' champs');
await p.locator('.stp[data-go="1"]').click(); await p.waitForTimeout(150);
await p.click('.js-tva[data-v="non"]');
await p.locator('.stp[data-go="2"]').click(); await p.waitForTimeout(300);

// ---- remise à zéro de la démonstration ----
const aTraiter=async()=>parseInt(
  (await p.locator('.js-wstabs .optab').nth(1).innerText()).replace(/\D/g,''),10);
const reste=await aTraiter();
t('des lignes ont bien été traitées pendant le test', reste < 12, reste+' restantes sur 12');
await p.click('.js-raz'); await p.waitForTimeout(250);
await p.click('.js-modal-ok'); await p.waitForTimeout(900);
t('la remise à zéro garde la session', !(await p.locator('.js-auth').isVisible()));
await p.locator('[data-name="LMNP_DUPONT_2026"]').click(); await p.waitForTimeout(400);
await p.click('.step[data-s="1"] .js-next'); await p.waitForTimeout(400);
t('toutes les opérations repartent à traiter', (await aTraiter())===12, await aTraiter()+' à traiter');
t('l\'historique d\'import est effacé', !(await p.locator('.js-dupbtn').isVisible()));

// ---- tient dans l'écran ----
t('étape 2 tient dans l\'écran',
  !(await p.evaluate(()=>document.documentElement.scrollHeight>window.innerHeight+2)));
console.log(R.join('\n'));
console.log('\nERREURS JS: '+(errs.length?errs.join('\n'):'aucune'));
await b.close();
