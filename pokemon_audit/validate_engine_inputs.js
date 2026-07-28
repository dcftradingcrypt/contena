'use strict';
const fs = require('fs');
const child = require('child_process');
const calc = require('/mnt/data/damage_calc_repo/calc/dist');
const data = JSON.parse(fs.readFileSync('/mnt/data/formal_audit_data/opponent_builds.json', 'utf8'));
const team = JSON.parse(fs.readFileSync('/mnt/data/formal_audit_data/team_config_formal.json', 'utf8'));
let gen;
try { gen = calc.Generations.get(0); } catch (_) { gen = calc.Generations.get('champions'); }
const errors = [];
const speciesResolved = {};
const moveMeta = {};
function getSpecies(name) { try { const s = gen.species.get(calc.toID(name)); return s && s.name ? s : null; } catch (_) { return null; } }
function resolveSpecies(raw) {
  const v = String(raw || '');
  const candidates = [v,
    v.replace(/ Alolan$/i, '-Alola').replace(/^Alolan /i, '').replace(/ Alola$/i, '-Alola'),
    v.replace(/ Galarian$/i, '-Galar').replace(/^Galarian /i, '').replace(/ Galar$/i, '-Galar'),
    v.replace(/ Hisuian$/i, '-Hisui').replace(/^Hisuian /i, '').replace(/ Hisui$/i, '-Hisui'),
    v.replace(/ Female$/i, '-F').replace(/ Male$/i, '-M'),
    v.replace(/ Shield Forme$/i, '-Shield').replace(/ Blade Forme$/i, '-Blade'),
    v.replace(/ Wash Rotom$/i, 'Rotom-Wash').replace(/ Heat Rotom$/i, 'Rotom-Heat'),
    v.replace(/ Frost Rotom$/i, 'Rotom-Frost').replace(/ Mow Rotom$/i, 'Rotom-Mow').replace(/ Fan Rotom$/i, 'Rotom-Fan'),
    v.replace(/ /g, '-')];
  for (const c of candidates) { const s = getSpecies(c); if (s) return s.name; }
  return null;
}
function evs(points) { return {hp:+points.hp, atk:+points.atk, def:+points.def, spa:+points.spa, spd:+points.spd, spe:+points.spe}; }
function equalStats(actual, expected) { return ['hp','atk','def','spa','spd','spe'].every(k => +actual[k] === +expected[k]); }
for (const m of team.members) {
  if (!Array.isArray(m.moves) || m.moves.length !== 4) errors.push({kind:'team_moves', member:m.id, moves:m.moves});
  const total = Object.values(m.points).reduce((a,b)=>a+Number(b),0); if (total !== 66) errors.push({kind:'team_points', member:m.id, total});
  const probes = [
    ['base',m.base_species,m.ability,m.expected_base_stats],
    ['standing',m.standing_species,m.standing_ability,m.standing_species.includes('-Mega')?m.expected_mega_stats:m.expected_base_stats],
    ['switch',m.switch_entry_species,m.ability,m.switch_entry_species.includes('-Mega')?m.expected_mega_stats:m.expected_base_stats],
    ['post',m.post_survival_species,m.post_survival_ability,m.post_survival_species.includes('-Mega')?m.expected_mega_stats:m.expected_base_stats]];
  for (const [kind,species,ability,expected] of probes) {
    if (!expected) continue;
    try { const p=new calc.Pokemon(gen,species,{level:50,item:m.item,ability,nature:m.nature,evs:evs(m.points)}); if(!equalStats(p.rawStats,expected))errors.push({kind:'team_stats',member:m.id,state:kind,species,actual:p.rawStats,expected}); }
    catch(error){errors.push({kind:'team_state',member:m.id,state:kind,species,ability,error:String(error)});}
  }
  for(const moveName of m.moves){const move=gen.moves.get(calc.toID(moveName));if(!move||!move.name)errors.push({kind:'team_move',member:m.id,move:moveName});}
}
for(const op of data.opponents){
  const resolved=resolveSpecies(op.engine_species)||resolveSpecies(op.pokemon_en);
  if(!resolved)errors.push({kind:'species',rank:op.rank,slug:op.slug,raw:op.engine_species,english:op.pokemon_en});else speciesResolved[String(op.rank)]=resolved;
  if(!Array.isArray(op.moves)||op.moves.length!==4)errors.push({kind:'opponent_moves',rank:op.rank,moves:op.moves});
  for(const name of op.moves||[]){try{const mv=gen.moves.get(calc.toID(name));if(!mv||!mv.name)errors.push({kind:'move',rank:op.rank,name});else moveMeta[name]={name:mv.name,type:mv.type,category:mv.category,bp:mv.bp,accuracy:mv.accuracy,priority:mv.priority,multihit:mv.multihit,flags:mv.flags};}catch(error){errors.push({kind:'move',rank:op.rank,name,error:String(error)});}}
}
for(const b of data.builds){
  const base=speciesResolved[String(b.opponent_rank)];if(!base)continue;let forme=base;try{forme=calc.Pokemon.getForme(gen,base,b.item,b.moves[0])||base}catch(_){}
  const sd=getSpecies(forme)||getSpecies(base);let ability=b.ability;if(sd&&sd.abilities&&!Object.values(sd.abilities).includes(ability))ability=Object.values(sd.abilities).filter(Boolean)[0]||ability;
  const e={hp:+b.hp_points,atk:+b.attack_points,def:+b.defense_points,spa:+b.sp_atk_points,spd:+b.sp_def_points,spe:+b.speed_points};
  try{const p=new calc.Pokemon(gen,forme,{level:50,item:b.item,ability,nature:b.nature,evs:e});if(!p.rawStats||!p.rawStats.hp)throw new Error('missing raw stats');}
  catch(error){errors.push({kind:'build',build_id:b.build_id,base,forme,item:b.item,ability,nature:b.nature,error:String(error)});}
}
const engineCommit=child.execFileSync('git',['-C','/mnt/data/damage_calc_repo','rev-parse','HEAD'],{encoding:'utf8'}).trim();
const output={generation:{num:gen.num,name:gen.name},engine_commit:engineCommit,team_count:team.members.length,opponent_count:data.opponents.length,build_count:data.builds.length,speciesResolved,moveMeta,errorCount:errors.length,errors:errors.slice(0,500)};
fs.writeFileSync('/mnt/data/formal_audit_data/engine_input_validation.json',JSON.stringify(output,null,2));
if(errors.length)throw new Error(`engine input validation failed (${errors.length}): ${JSON.stringify(errors.slice(0,12))}`);
console.log(JSON.stringify({generation:output.generation,engine_commit:engineCommit,opponents:data.opponents.length,builds:data.builds.length}));
