from driver import *

def main():
 state=read(BASE/'search_state.json');row=next(r for r in state['variants'] if r['name']=='R5_SUSTAIN_H3240')
 common={'candidate_id':row['check']['candidate_id'],'candidate_sha256':row['check']['candidate_sha256'],'limit':200}
 queries=[('leaks',{'event_type':'ENEMY_LEAK'}),('kills',{'event_type':'ENEMY_DEATH'}),('blocks',{'event_type':'BLOCK'}),('protected',{'event_type':'PROTECTED_TARGET_REACHED'}),('roadblocks',{'event_type':'DEVICE_DESTROYED'}),('operator_deaths',{'event_type':'OPERATOR_DEATH'}),('artillery_damage',{'event_type':'DAMAGE','target_id':'enemy_1112_emppnt#0','aggregate':{'field':'details.amount'}}),('cannon_born',{'event_type':'PROJECTILE_BORN','source_id':'enemy_1112_emppnt#0'}),('cannon_hits',{'event_type':'ENEMY_ABILITY_HIT','source_id':'enemy_1112_emppnt#0'}),('midnight_heal',{'event_type':'HEAL','target_id':MID})]
 coverage=[]
 for name,filters in queries:
  all_events=[];offset=0;pages=[]
  while True:
   response=shared.tool('query_events',{**common,**filters,'offset':offset},'evidence_'+name+'_'+str(offset))
   assert response['observation_coverage']=='COMPLETE'
   pages.append(response);all_events.extend(response['events'])
   if response['pagination']['next_offset'] is None:break
   offset += response['pagination']['returned_matches']
   if not response['pagination']['returned_matches']:raise RuntimeError('No pagination progress')
  assert len(all_events)==response['pagination']['total_matches']
  coverage.append({'query':name,'filters':filters,'matches':len(all_events),'pages':len(pages),'observation_coverage':'COMPLETE','events':all_events,'aggregate':response.get('aggregate')})
 write(BASE/'production_query_evidence_v1.json',coverage)
 status=shared.tool('get_session_status',{},'final_status')
 write(BASE/'final_status_v1.json',status)
 print({'queries':len(coverage),'pages':sum(r['pages'] for r in coverage),'counts':(status['check_call_ledger']['used_check_calls'],status['candidate_ledger']['used_candidates'],status['budget']['started_stage_simulations'])})

if __name__=='__main__':main()
