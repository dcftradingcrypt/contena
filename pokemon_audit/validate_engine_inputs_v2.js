'use strict';
const fs = require('fs');
const path = require('path');
const child = require('child_process');
const calc = require('/mnt/data/damage_calc_repo/calc/dist');
const data = JSON.parse(fs.readFileSync('/mnt/data/formal_audit_data/opponent_builds.json', 'utf8'));
const team = JSON.parse(fs.readFileSync('/mnt/data/formal_audit_data/team_config_formal.json', 'utf8'));
let gen;
try { gen = calc.Generations.get(0); } catch (_) { gen = calc.Generations.get('champions'); }
const errors = [];
const speciesResolved = {};
const speciesCandidates = {};
const moveMeta = {};
function getSpecies(name) {
  try {
    const s = gen.species.get(calc.toID(name));
    return s && s.name ? s : null;
  } catch (_) { return null; }
}
function wordsTitle(s) {
  return String(s || '').split(/[-_ ]+/).filter(Boolean).map(x => x.charAt(0).toUpperCase() + x.slice(1).toLowerCase()).join('-');
}
function genericCandidates(raw) {
  const v = String(raw || '').trim();
  if (!v) return [];
  const out = [v, v.replace(/ /g, '-'), wordsTitle(v)];
  const lower = v.toLowerCase();
  const suffixes = [
    ['-alolan', '-Alola'], [' alolan', '-Alola'],
    ['-galarian', '-Galar'], [' galarian', '-Galar'],
    ['-hisui', '-Hisui'], [' hisui', '-Hisui'], ['-hisuian', '-Hisui'], [' hisuian', '-Hisui'],
  ];
  for (const [suffix, replacement] of suffixes) {
    if (lower.endsWith(suffix)) {
      const base = v.slice(0, v.length - suffix.length).replace(/^alolan[ -]/i, '').replace(/^galarian[ -]/i, '').replace(/^hisuian[ -]/i, '');
      out.push(wordsTitle(base) + replacement);
    }
  }
  if (/^alolan[ -]/i.test(v)) out.push(wordsTitle(v.replace(/^alolan[ -]/i, '')) + '-Alola');
  if (/^galarian[ -]/i.test(v)) out.push(wordsTitle(v.replace(/^galarian[ -]/i, '')) + '-Galar');
  if (/^hisuian[ -]/i.test(v)) out.push(wordsTitle(v.replace(/^hisuian[ -]/i, '')) + '-Hisui');
  if (/^rotom[- ]/i.test(v)) out.push('Rotom-' + wordsTitle(v.replace(/^rotom[- ]/i, '')));
  if (/[- ]rotom$/i.test(v)) out.push('Rotom-' + wordsTitle(v.replace(/[- ]rotom$/i, '')));
  if (/[- ]male$/i.test(v)) {
    const base = wordsTitle(v.replace(/[- ]male$/i, ''));
    out.push(base, base + '-M');
  }
  if (/[- ]female$/i.test(v)) {
    const base = wordsTitle(v.replace(/[- ]female$/i, ''));
    out.push(base + '-F');
  }
  if (/shield forme/i.test(v)) out.push(wordsTitle(v.replace(/shield forme/i, '').trim()) + '-Shield');
  if (/blade forme/i.test(v)) out.push(wordsTitle(v.replace(/blade forme/i, '').trim()) + '-Blade');
  if (/family of four/i.test(v)) out.push(wordsTitle(v.replace(/family of four/i, '').trim()) + '-Four');
  if (/eternal flower/i.test(v)) out.push(wordsTitle(v.replace(/eternal flower/i, '').trim()) + '-Eternal');
  if (/hangry/i.test(v)) out.push(wordsTitle(v.replace(/hangry(?: form)?/i, '').trim()) + '-Hangry');
  return [...new Set(out.filter(Boolean))];
}
function mappingFormCandidates(op) {
  const out = [];
  const rel = op.mapping_file;
  if (!rel) return out;
  const full = path.join('/mnt/data/battledata_repo', rel);
  if (!fs.existsSync(full)) return out;
  try {
    const record = JSON.parse(fs.readFileSync(full, 'utf8'));
    const forms = (((record || {}).summary || {}).forms || []);
    const exact = forms.filter(f => String(f.slug || '') === String(op.slug || ''));
    const selected = exact.length ? exact : forms.filter(f => calc.toID(f.form_name || f.saved_name || '') === calc.toID(op.pokemon_en || ''));
    for (const f of selected) {
      out.push(f.slug, f.form_name, f.saved_name, f.title);
      const bracket = String(f.title || '').match(/\[([^\]]+)\]/);
      if (bracket) out.push(bracket[1]);
    }
  } catch (_) {}
  return out;
}
function resolveOpponent(op) {
  const raw = [op.slug, op.pokemon_en, op.engine_species, ...mappingFormCandidates(op)];
  const candidates = [];
  for (const value of raw) candidates.push(...genericCandidates(value));
  if (String(op.slug) === 'aegislash' && /shield/i.test(String(op.pokemon_en))) candidates.unshift('Aegislash-Shield');
  if (String(op.slug).includes('family-of-four')) candidates.unshift('Maushold-Four');
  if (String(op.slug).includes('eternal-flower')) candidates.unshift('Floette-Eternal');
  for (const candidate of [...new Set(candidates)]) {
    const s = getSpecies(candidate);
    if (s) return {name: s.name, candidates};
  }
  return {name: null, candidates};
}
function evs(points) { return {hp:+points.hp, atk:+points.atk, def:+points.def, spa:+points.spa, spd:+points.spd, spe:+points.spe}; }
function equalStats(actual, expected) { return ['hp','atk','def','spa','spd','spe'].every(k => +actual[k] === +expected[k]); }
function validAbility(species, ability) {
  const s = getSpecies(species);
  return !!(s && s.abilities && Object.values(s.abilities).filter(Boolean).includes(ability));
}
for (const m of team.members) {
  if (!Array.isArray(m.moves) || m.moves.length !== 4) errors.push({kind:'team_moves', member:m.id, moves:m.moves});
  const total = Object.values(m.points).reduce((a,b)=>a+Number(b),0);
  if (total !== 66) errors.push({kind:'team_points', member:m.id, total});
  const probes = [
    ['base',m.base_species,m.ability,m.expected_base_stats],
    ['standing',m.standing_species,m.standing_ability,m.standing_species.includes('-Mega')?m.expected_mega_stats:m.expected_base_stats],
    ['switch',m.switch_entry_species,m.ability,m.switch_entry_species.includes('-Mega')?m.expected_mega_stats:m.expected_base_stats],
    ['post',m.post_survival_species,m.post_survival_ability,m.post_survival_species.includes('-Mega')?m.expected_mega_stats:m.expected_base_stats]
  ];
  for (const [kind,species,ability,expected] of probes) {
    if (!expected) continue;
    try {
      const resolved = getSpecies(species);
      if (!resolved) throw new Error('species not found');
      if (!validAbility(species, ability)) throw new Error(`ability ${ability} not valid for ${species}; valid=${JSON.stringify(resolved.abilities)}`);
      const p = new calc.Pokemon(gen,species,{level:50,item:m.item,ability,nature:m.nature,evs:evs(m.points)});
      if (!equalStats(p.rawStats,expected)) errors.push({kind:'team_stats',member:m.id,state:kind,species,actual:p.rawStats,expected});
    } catch(error) { errors.push({kind:'team_state',member:m.id,state:kind,species,ability,error:String(error)}); }
  }
  for (const moveName of m.moves) {
    const move = gen.moves.get(calc.toID(moveName));
    if (!move || !move.name) errors.push({kind:'team_move',member:m.id,move:moveName});
  }
}
for (const op of data.opponents) {
  const resolved = resolveOpponent(op);
  speciesCandidates[String(op.rank)] = resolved.candidates;
  if (!resolved.name) errors.push({kind:'species',rank:op.rank,slug:op.slug,raw:op.engine_species,english:op.pokemon_en,candidates:resolved.candidates});
  else speciesResolved[String(op.rank)] = resolved.name;
  if (!Array.isArray(op.moves) || op.moves.length !== 4) errors.push({kind:'opponent_moves',rank:op.rank,moves:op.moves});
  for (const name of op.moves || []) {
    try {
      const mv = gen.moves.get(calc.toID(name));
      if (!mv || !mv.name) errors.push({kind:'move',rank:op.rank,name});
      else moveMeta[name] = {name:mv.name,type:mv.type,category:mv.category,bp:mv.bp,accuracy:mv.accuracy,priority:mv.priority,multihit:mv.multihit,flags:mv.flags};
    } catch(error) { errors.push({kind:'move',rank:op.rank,name,error:String(error)}); }
  }
}
const buildResolved = {};
for (const b of data.builds) {
  const base = speciesResolved[String(b.opponent_rank)];
  if (!base) continue;
  let forme = base;
  try { forme = calc.Pokemon.getForme(gen,base,b.item,b.moves[0]) || base; } catch (_) {}
  const sd = getSpecies(forme) || getSpecies(base);
  let ability = b.ability;
  if (sd && sd.abilities && !Object.values(sd.abilities).filter(Boolean).includes(ability)) ability = Object.values(sd.abilities).filter(Boolean)[0] || ability;
  const e = {hp:+b.hp_points,atk:+b.attack_points,def:+b.defense_points,spa:+b.sp_atk_points,spd:+b.sp_def_points,spe:+b.speed_points};
  try {
    const p = new calc.Pokemon(gen,forme,{level:50,item:b.item,ability,nature:b.nature,evs:e});
    if (!p.rawStats || !p.rawStats.hp) throw new Error('missing raw stats');
    buildResolved[b.build_id] = {base, forme, ability, rawStats:p.rawStats};
  } catch(error) { errors.push({kind:'build',build_id:b.build_id,base,forme,item:b.item,ability,nature:b.nature,error:String(error)}); }
}
const engineCommit = child.execFileSync('git',['-C','/mnt/data/damage_calc_repo','rev-parse','HEAD'],{encoding:'utf8'}).trim();
const output = {generation:{num:gen.num,name:gen.name},engine_commit:engineCommit,team_count:team.members.length,opponent_count:data.opponents.length,build_count:data.builds.length,speciesResolved,speciesCandidates,buildResolved,moveMeta,errorCount:errors.length,errors:errors.slice(0,500)};
fs.writeFileSync('/mnt/data/formal_audit_data/engine_input_validation.json',JSON.stringify(output,null,2));
if (errors.length) throw new Error(`engine input validation failed (${errors.length}): ${JSON.stringify(errors.slice(0,12))}`);
console.log(JSON.stringify({generation:output.generation,engine_commit:engineCommit,opponents:data.opponents.length,builds:data.builds.length,resolved:Object.keys(speciesResolved).length}));
