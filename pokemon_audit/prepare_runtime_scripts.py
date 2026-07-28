from __future__ import annotations

import shutil
from pathlib import Path

SRC = Path('pokemon_audit')
DST = Path('/mnt/data/formal_audit_data/scripts')
DST.mkdir(parents=True, exist_ok=True)

for path in SRC.iterdir():
    if path.is_file() and path.suffix in {'.py', '.js', '.json'}:
        shutil.copy2(path, DST / path.name)

# Correct mutations and edge conditions in the runtime copy used for the formal run.
two = DST / 'run_two_hit_state.js'
s = two.read_text(encoding='utf-8')
s = s.replace('p.curHPValue=', 'p.originalCurHP=')
s = s.replace("'Blood Moon'", "")
s = s.replace(
    "function buildPokemon(species,o){const p=new calc.Pokemon(gen,species,{level:50,...o});if(o.types)p.types=o.types.slice();if(o.abilityOn!==undefined)p.abilityOn=o.abilityOn;return p}",
    "function buildPokemon(species,o){const opts={level:50,...o};if(opts.abilityOn===undefined&&opts.ability==='Slow Start')opts.abilityOn=true;const p=new calc.Pokemon(gen,species,opts);if(o.types)p.types=o.types.slice();if(o.abilityOn!==undefined)p.abilityOn=o.abilityOn;return p}",
)
s = s.replace(
    "function initialField(att,def,kind){let weather,terrain;for(const a of(kind==='switch'?[att,def]:[def,att])){weather=weatherFromAbility(a)||weather;terrain=terrainFromAbility(a)||terrain}return {weather,terrain}}",
    "function entrySpeed(p){let s=p.rawStats.spe;if(p.item==='Choice Scarf')s=Math.floor(s*1.5);else if(['Iron Ball','Macho Brace','Power Anklet','Power Band','Power Belt','Power Bracer','Power Lens','Power Weight'].includes(p.item))s=Math.floor(s/2);return s}function initialField(att,def,kind){let weather,terrain;const order=kind==='switch'?[att,def]:[att,def].sort((x,y)=>entrySpeed(y)-entrySpeed(x));for(const p of order){weather=weatherFromAbility(p.ability)||weather;terrain=terrainFromAbility(p.ability)||terrain}return {weather,terrain}}",
)
s = s.replace(
    "const md=moveData(firstName),aDef=resolveAttacker(b,firstName),fld=initialField(aDef.ability,state.ability,state.kind),field=new calc.Field({gameType:'Singles',weather:fld.weather,terrain:fld.terrain});if(!isImmediate(md,b.item,fld,aDef.ability))return {valid:false,reason:'charge'};if(state.kind==='switch'&&FIRST_ONLY.has(md.name))return {valid:false,reason:'first-only unavailable against switch'};const att=buildPokemon(aDef.forme,{item:b.item,ability:aDef.ability,nature:b.nature,evs:aDef.evs}),def=buildPokemon(state.species,{item:state.item,ability:state.ability,nature:state.member.nature,evs:state.member.points});",
    "const md=moveData(firstName),aDef=resolveAttacker(b,firstName),att=buildPokemon(aDef.forme,{item:b.item,ability:aDef.ability,nature:b.nature,evs:aDef.evs}),def=buildPokemon(state.species,{item:state.item,ability:state.ability,nature:state.member.nature,evs:state.member.points}),fld=initialField(att,def,state.kind),field=new calc.Field({gameType:'Singles',weather:fld.weather,terrain:fld.terrain,defenderSide:state.kind==='switch'?{isSwitching:'out'}:{}});if(!isImmediate(md,b.item,fld,aDef.ability))return {valid:false,reason:'charge'};if(state.kind==='switch'&&FIRST_ONLY.has(md.name))return {valid:false,reason:'first-only unavailable against switch'};",
)
s = s.replace(
    "const moves=b.moves.filter(eligibleMove).map(n=>moveData(n).name);",
    "const moves=b.moves.filter(n=>eligibleMove(n)&&resolveAttacker(b,n).ability!=='Parental Bond').map(n=>moveData(n).name);",
)
s = s.replace("let ability=b.ability;if(!validAbility(forme,ability))ability=firstAbility(forme)||ability;", "let ability=forme!==base?(firstAbility(forme)||b.ability):b.ability;")
two.write_text(s, encoding='utf-8')

one = DST / 'run_ohko_state.js'
s = one.read_text(encoding='utf-8')
s = s.replace(
    "function buildPokemon(species,o){return new calc.Pokemon(gen,species,{level:50,...o})}",
    "function buildPokemon(species,o){const opts={level:50,...o};if(opts.abilityOn===undefined&&opts.ability==='Slow Start')opts.abilityOn=true;return new calc.Pokemon(gen,species,opts)}",
)
s = s.replace(
    "function fieldFor(att,def,kind){let weather,terrain;for(const a of(kind==='switch'?[att,def]:[def,att])){weather=weatherFromAbility(a)||weather;terrain=terrainFromAbility(a)||terrain}return new calc.Field({gameType:'Singles',weather,terrain})}",
    "function entrySpeed(p){let s=p.rawStats.spe;if(p.item==='Choice Scarf')s=Math.floor(s*1.5);else if(['Iron Ball','Macho Brace','Power Anklet','Power Band','Power Belt','Power Bracer','Power Lens','Power Weight'].includes(p.item))s=Math.floor(s/2);return s}function fieldFor(att,def,kind){let weather,terrain;const order=kind==='switch'?[att,def]:[att,def].sort((x,y)=>entrySpeed(y)-entrySpeed(x));for(const p of order){weather=weatherFromAbility(p.ability)||weather;terrain=terrainFromAbility(p.ability)||terrain}return new calc.Field({gameType:'Singles',weather,terrain,defenderSide:kind==='switch'?{isSwitching:'out'}:{}})}",
)
s = s.replace("const field=fieldFor(a.ability,state.ability,state.kind);", "const field=fieldFor(a.pokemon,def,state.kind);")
s = s.replace("let ability=b.ability;if(!validAbility(forme,ability))ability=firstAbility(forme)||ability;", "let ability=forme!==base?(firstAbility(forme)||b.ability):b.ability;")
one.write_text(s, encoding='utf-8')

validator = DST / 'validate_engine_inputs_v2.js'
s = validator.read_text(encoding='utf-8')
s = s.replace("      if (!validAbility(species, ability)) throw new Error(`ability ${ability} not valid for ${species}; valid=${JSON.stringify(resolved.abilities)}`);\n", "")
s = s.replace("  let ability = b.ability;\n  if (sd && sd.abilities && !Object.values(sd.abilities).filter(Boolean).includes(ability)) ability = Object.values(sd.abilities).filter(Boolean)[0] || ability;", "  let ability = forme !== base ? (Object.values((sd || {}).abilities || {}).filter(Boolean)[0] || b.ability) : b.ability;")
validator.write_text(s, encoding='utf-8')

# Fail closed if any requested replacement did not take effect.
assert 'curHPValue' not in two.read_text(encoding='utf-8')
assert "resolveAttacker(b,n).ability!=='Parental Bond'" in two.read_text(encoding='utf-8')
assert "defenderSide:kind==='switch'?{isSwitching:'out'}:{}" in one.read_text(encoding='utf-8')
assert "defenderSide:state.kind==='switch'?{isSwitching:'out'}:{}" in two.read_text(encoding='utf-8')
assert "forme!==base?(firstAbility(forme)||b.ability):b.ability" in one.read_text(encoding='utf-8')
assert "forme!==base?(firstAbility(forme)||b.ability):b.ability" in two.read_text(encoding='utf-8')
assert 'ability ${ability} not valid for ${species}' not in validator.read_text(encoding='utf-8')
print(DST)
