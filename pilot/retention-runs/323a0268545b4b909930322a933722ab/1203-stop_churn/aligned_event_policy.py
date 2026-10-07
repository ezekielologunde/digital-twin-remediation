"""Conservative lifecycle invalidation; receives observations, never fault labels."""
ADVERSE={'die','stop','kill','pause','oom','destroy','restart','update','unpause','start'}

def decide(evidence,events,dependency_ids,cursor,running,available_at,decision_time,late):
    verified=all(v['verified'] is True for v in evidence.values())
    changes=[e for e in events if e.get('Type')=='container' and
             e.get('Actor',{}).get('ID') in dependency_ids and
             e.get('Action','').split(':',1)[0] in ADVERSE and int(e.get('timeNano',0))>cursor]
    def answer(value):return {'decision':'approve' if value else 'abstain'}
    return {
        'final_checks':answer(verified),
        'late_functional_recheck':answer(all(v['verified'] is True for v in late.values())),
        'fresh_running_state':answer(verified and all(running.values())),
        'events_available':answer(verified and not changes),
        'events_delayed':answer(verified and not (changes if decision_time>=available_at else [])),
        'events_silently_dropped':answer(verified)},changes
