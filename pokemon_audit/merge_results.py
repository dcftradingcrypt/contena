from __future__ import annotations
import csv,json,subprocess
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any
BASE=Path('/mnt/data');ROOT=BASE/'formal_audit_data';INPUTS=BASE/'formal_inputs'/'formal_snapshot';OHKO=ROOT/'ohko_parts';TWO=ROOT/'two_hit_parts'
TEAM=json.loads((ROOT/'team_config_formal.json').read_text(encoding='utf-8'));BUILDS=json.loads((ROOT/'opponent_builds.json').read_text(encoding='utf-8'));SNAPSHOT=json.loads((INPUTS/'snapshot_manifest.json').read_text(encoding='utf-8'));JST=timezone(timedelta(hours=9))
STATES=[f"standing_{m['id']}" for m in TEAM['members']]+[f"switch_{m['id']}" for m in TEAM['members']]
EXCLUDED_TWO={'Counter','Mirror Coat','Metal Burst','Comeuppance','Bide','Fissure','Guillotine','Horn Drill','Sheer Cold','Future Sight','Doom Desire','Sucker Punch','Thunderclap','Upper Hand'}
def read_csv(path):
 with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_csv(path,rows,fieldnames=None):
 fieldnames=fieldnames or (list(rows[0]) if rows else [])
 with Path(path).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fieldnames);w.writeheader();w.writerows(rows)
def merge_csv(parts,suffix,out):
 count=0;header=None
 with Path(out).open('w',encoding='utf-8-sig',newline='') as fo:
  writer=None
  for st in STATES:
   p=Path(parts)/f'{st}_{suffix}.csv';rows=read_csv(p)
   if header is None:
    with p.open(encoding='utf-8-sig',newline='') as f:header=next(csv.reader(f))
    writer=csv.DictWriter(fo,fieldnames=header);writer.writeheader()
   for row in rows:writer.writerow(row);count+=1
 return count
def iv(v,d=0):return d if v in ('',None) else int(float(v))
def fv(v,d=0.0):return d if v in ('',None) else float(v)
def main():
 raw_count=merge_csv(OHKO,'damage_routes_raw',ROOT/'damage_routes_raw.csv');ohko_route_count=merge_csv(OHKO,'ohko_routes',ROOT/'ohko_routes.csv');two_route_count=merge_csv(TWO,'two_hit_routes',ROOT/'two_hit_routes.csv')
 ohko_s=[json.loads((OHKO/f'{s}_summary.json').read_text()) for s in STATES];two_s=[json.loads((TWO/f'{s}_summary.json').read_text()) for s in STATES];ohko_pairs=[r for s in ohko_s for r in s['pairs']];two_pairs=[r for s in two_s for r in s['pairs']]
 if len(ohko_pairs)!=1200 or len({(r['state_id'],int(r['opponent_rank'])) for r in ohko_pairs})!=1200:raise RuntimeError('OHKO pair matrix invalid')
 write_csv(ROOT/'ohko_state_matrix.csv',ohko_pairs,sorted(set().union(*(r.keys() for r in ohko_pairs))));write_csv(ROOT/'two_hit_state_matrix.csv',two_pairs,sorted(set().union(*(r.keys() for r in two_pairs))))
 top={int(r['rank']):r for r in read_csv(INPUTS/'top100.csv')};members={m['id']:m for m in TEAM['members']};oi={(r['state_id'],int(r['opponent_rank'])):r for r in ohko_pairs};ti={(r['state_id'],int(r['opponent_rank'])):r for r in two_pairs}
 max_loss=defaultdict(float)
 for r in read_csv(ROOT/'damage_routes_raw.csv'):max_loss[(r['state_id'],int(r['opponent_rank']))]=max(max_loss[(r['state_id'],int(r['opponent_rank']))],fv(r.get('max_effective_loss_pct')))
 state_rows=[]
 for st in STATES:
  kind,mid=st.split('_',1);m=members[mid]
  for rank in range(1,101):
   o=oi[(st,rank)];route=o;stage='ohko' if o.get('classification') else ''
   if not stage:
    t=ti.get((st,rank))
    if t and t.get('classification'):route=t;stage='two_hit'
   cls=route.get('classification') or '該当なし';risk=iv(route.get('risk_tier'))
   state_rows.append({'state_id':st,'state_kind':kind,'member_order':m['order'],'member_id':mid,'member_name_ja':m['name_ja'],'opponent_rank':rank,'opponent_slug':top[rank]['slug'],'opponent_name_ja':top[rank]['name_ja'],'opponent_name_en':top[rank]['name_en'],'classification':cls,'risk_tier':risk,'source_stage':stage or 'none','max_first_loss_pct':round(max_loss[(st,rank)],6),'build_id':route.get('build_id',''),'attacker_species':route.get('attacker_species',''),'attacker_item':route.get('attacker_item',''),'attacker_ability':route.get('attacker_ability_resolved') or route.get('attacker_ability',''),'attacker_nature':route.get('attacker_nature',''),'move':route.get('move',''),'first_move':route.get('first_move',''),'second_move':route.get('second_move',''),'ko_numerator':route.get('ko_rolls') or route.get('kill_paths') or '','ko_denominator':route.get('roll_denominator') or route.get('path_denominator') or '','multi_boundary':route.get('multi_boundary',''),'notes':route.get('notes','')})
 if len(state_rows)!=1200:raise RuntimeError('state matrix count')
 write_csv(ROOT/'state_matrix.csv',state_rows);idx={(r['state_id'],int(r['opponent_rank'])):r for r in state_rows}
 recs=[];threats=[]
 for active in TEAM['members']:
  for rank in range(1,101):
   current=idx[(f"standing_{active['id']}",rank)]
   if int(current['risk_tier'])==0:rec={'active_member_order':active['order'],'active_member_id':active['id'],'active_member_name_ja':active['name_ja'],'opponent_rank':rank,'opponent_name_ja':top[rank]['name_ja'],'current_classification':'該当なし','current_risk_tier':0,'best_switch_id':'','best_switch_name_ja':'','best_switch_classification':'','best_switch_risk_tier':'','best_switch_max_first_loss_pct':'','display':'居座り可','candidate_order':''}
   else:
    c=[]
    for cand in TEAM['members']:
     if cand['id']==active['id']:continue
     x=idx[(f"switch_{cand['id']}",rank)];c.append((int(x['risk_tier']),float(x['max_first_loss_pct']),int(cand['order']),cand,x))
    c.sort(key=lambda z:(z[0],z[1],z[2]));risk,loss,_,cand,x=c[0]
    display='○ 安定交代' if risk==0 else ('△ 最も安全（2パン圏は残る）' if risk<=2 else ('△ 条件付き1パンが残る' if risk==3 else '× 安定交代なし'))
    rec={'active_member_order':active['order'],'active_member_id':active['id'],'active_member_name_ja':active['name_ja'],'opponent_rank':rank,'opponent_name_ja':top[rank]['name_ja'],'current_classification':current['classification'],'current_risk_tier':current['risk_tier'],'best_switch_id':cand['id'],'best_switch_name_ja':cand['name_ja'],'best_switch_classification':x['classification'],'best_switch_risk_tier':risk,'best_switch_max_first_loss_pct':round(loss,6),'display':display,'candidate_order':' > '.join(f"{z[3]['name_ja']}:{z[4]['classification']}/{z[1]:.3f}%" for z in c)};threats.append({**current,**{f'switch_{k}':v for k,v in rec.items()}})
   recs.append(rec)
 if len(recs)!=600:raise RuntimeError('switch count')
 write_csv(ROOT/'switch_recommendations.csv',recs);write_csv(ROOT/'threats_with_switch.csv',threats,sorted(set().union(*(r.keys() for r in threats))) if threats else [])
 summary=[]
 for m in TEAM['members']:
  rows=[r for r in state_rows if r['state_id']==f"standing_{m['id']}"]
  summary.append({'member_order':m['order'],'member_id':m['id'],'member_name_ja':m['name_ja'],'確1':sum(r['classification']=='確1' for r in rows),'乱1':sum(r['classification']=='乱1' for r in rows),'条件/連続技1パン':sum('条件' in r['classification'] or '連続技' in r['classification'] for r in rows),'確2':sum(r['classification']=='確2' for r in rows),'乱2':sum(r['classification']=='乱2' for r in rows),'該当なし':sum(r['classification']=='該当なし' for r in rows),'危険合計':sum(int(r['risk_tier'])>0 for r in rows)})
 write_csv(ROOT/'summary.csv',summary)
 ri={(r['active_member_id'],int(r['opponent_rank'])):r for r in recs};quick=[]
 for rank in range(1,101):
  row={'rank':rank,'opponent_name_ja':top[rank]['name_ja'],'opponent_name_en':top[rank]['name_en']}
  for m in TEAM['members']:
   r=ri[(m['id'],rank)];row[m['name_ja']]=r['display']+(f" {r['best_switch_name_ja']}" if r['best_switch_name_ja'] else '')
  quick.append(row)
 write_csv(ROOT/'quick_switch_top100.csv',quick)
 ohko_routes=read_csv(ROOT/'ohko_routes.csv');two_routes=read_csv(ROOT/'two_hit_routes.csv');ohko_keys={(r['state_id'],int(r['opponent_rank'])) for r in ohko_pairs if r.get('classification')};two_keys={(r['state_id'],int(r['opponent_rank'])) for r in two_pairs if r.get('classification')};overlap=ohko_keys&two_keys;badmoves=[r for r in two_routes if r.get('first_move') in EXCLUDED_TWO or r.get('second_move') in EXCLUDED_TWO];badpaths=[r for r in two_routes if not(1<=iv(r.get('kill_paths'))<=256) or (r.get('classification')=='確2' and iv(r.get('kill_paths'))!=256) or (r.get('classification')=='乱2' and not 1<=iv(r.get('kill_paths'))<=255)]
 classes=Counter(r['classification'] for r in state_rows);stages=Counter(r['source_stage'] for r in state_rows);engine=json.loads((ROOT/'engine_input_validation.json').read_text())
 checks=[('team_member_count',len(TEAM['members'])==6,f"actual={len(TEAM['members'])}"),('team_four_moves',all(len(m['moves'])==4 for m in TEAM['members']),''),('team_point_totals',all(sum(m['points'].values())==66 for m in TEAM['members']),''),('top100_count',len(top)==100 and set(top)==set(range(1,101)),f'actual={len(top)}'),('detail_capture_count',SNAPSHOT['detail_count']==100,f"actual={SNAPSHOT['detail_count']}"),('snapshot_synchronized',SNAPSHOT['all_detail_timestamps_match'] and SNAPSHOT['start_end_tier_identical'],SNAPSHOT['snapshot_jst']),('one_build_per_opponent',len(BUILDS['builds'])==100 and len({int(r['opponent_rank']) for r in BUILDS['builds']})==100,f"actual={len(BUILDS['builds'])}"),('engine_inputs',engine['errorCount']==0 and len(engine['speciesResolved'])==100,f"errors={engine['errorCount']} resolved={len(engine['speciesResolved'])}"),('ohko_state_pairs',len(ohko_pairs)==1200,f'actual={len(ohko_pairs)}'),('two_hit_no_ohko_overlap',not overlap,f'overlap={len(overlap)}'),('two_hit_excluded_moves_zero',not badmoves,f'actual={len(badmoves)}'),('two_hit_path_ranges',not badpaths,f'actual={len(badpaths)}'),('state_matrix_1200',len(state_rows)==1200 and len({(r['state_id'],r['opponent_rank']) for r in state_rows})==1200,''),('switch_recommendations_600',len(recs)==600,'')]
 checkrows=[{'check':n,'result':'PASS' if ok else 'FAIL','detail':d} for n,ok,d in checks];write_csv(ROOT/'validation_checks_pre_output.csv',checkrows);fails=[r for r in checkrows if r['result']!='PASS'];
 if fails:raise RuntimeError(f'validation failures: {fails}')
 damage_commit=subprocess.check_output(['git','-C','/mnt/data/damage_calc_repo','rev-parse','HEAD'],text=True).strip();mapping_commit=subprocess.check_output(['git','-C','/mnt/data/battledata_repo','rev-parse','HEAD'],text=True).strip()
 manifest={'schema_version':1,'status':'CORE_CALCULATION_COMPLETE_OUTPUT_PENDING','generated_at_jst':datetime.now(JST).replace(microsecond=0).isoformat(),'snapshot':SNAPSHOT,'battle_format':'Singles','level':50,'season':'M-4','regulation':'M-B','thresholds':BUILDS['thresholds'],'build_policy':'method_3_3_B_current_most_frequent_one_build_per_opponent','counts':{'opponents':100,'builds':len(BUILDS['builds']),'states':len(STATES),'state_pairs':len(state_rows),'raw_damage_routes':raw_count,'ohko_routes':ohko_route_count,'ohko_pairs':len(ohko_keys),'two_hit_routes':two_route_count,'two_hit_pairs':len(two_keys),'no_threat_pairs':classes['該当なし'],'switch_recommendations':len(recs)},'classification_counts':dict(classes),'stage_counts':dict(stages),'engine':{'repository':'smogon/damage-calc','commit':damage_commit,'generation':engine['generation']},'mapping':{'repository':'Gheist23/pokemonbattledata','commit':mapping_commit}}
 (ROOT/'core_validation.json').write_text(json.dumps({'result':'PASS','checks':checkrows,'counts':manifest['counts'],'classification_counts':dict(classes)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(ROOT/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'result':'PASS','counts':manifest['counts'],'classifications':dict(classes)},ensure_ascii=False))
if __name__=='__main__':main()
