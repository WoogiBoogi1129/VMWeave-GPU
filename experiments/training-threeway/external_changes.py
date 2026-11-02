"""Summarize observed Pod changes; do not infer their cause or application SLA."""
import json


def summarize(path,start,end):
    prior=None;baseline=False;checks=[];errors=[];events=[]
    def relevant(pod):
        return not ((pod['namespace']=='kube-system' and pod['name'].startswith('hami-device-plugin-')) or
                    (pod['namespace']=='gpu-operator' and pod['name'].startswith('nvidia-dcgm-exporter-')))
    for line in path.read_text().splitlines():
        try:row=json.loads(line)
        except json.JSONDecodeError:continue  # An active writer may have a partial last line.
        utc=row['utc']
        if utc>end:break
        if row.get('error'):
            if utc>=start:errors.append(row)
            continue
        if utc>=start:checks.append(utc)
        if row.get('pods') is None:continue  # Digest unchanged: prior full snapshot still applies.
        current={(p['namespace'],p['name']):p for p in row['pods'] if relevant(p)}
        if utc<start:baseline=True
        if prior is not None and utc>=start:
            changes=[]
            for key in sorted(prior.keys()|current.keys()):
                before,after=prior.get(key),current.get(key)
                if before!=after:changes.append({'namespace':key[0],'name':key[1],'before':before,'after':after})
            if changes:events.append({'utc':utc,'changes':changes})
        prior=current
    gaps=[b-a for a,b in zip(checks,checks[1:])]
    gaps+=([checks[0]-start,end-checks[-1]] if checks else [end-start])
    return {'start_utc':start,'end_utc':end,'baseline_before_formal':baseline,'successful_observations':len(checks),
            'max_observation_gap_seconds':max(gaps),
            'api_errors':errors,'change_events':events,
            'ignored_authorized_monitors':['kube-system/hami-device-plugin-*','gpu-operator/nvidia-dcgm-exporter-*'],
            'scope':'Observer already excludes this experiment. Here only authorized monitor Pods are additionally excluded. Changes are observations, not causal attribution. No performance samples are excluded.'}
