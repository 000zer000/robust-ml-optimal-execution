from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

OUT = Path('/mnt/data/research_paper/figures')
OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path('/mnt/data')

plt.rcParams.update({
    'font.size': 8.5,
    'axes.labelsize': 8.5,
    'axes.titlesize': 9.5,
    'legend.fontsize': 7.5,
    'xtick.labelsize': 7.5,
    'ytick.labelsize': 7.5,
    'figure.dpi': 160,
    'savefig.bbox': 'tight',
})

def save(name):
    plt.tight_layout()
    plt.savefig(OUT/f'{name}.pdf')
    plt.savefig(OUT/f'{name}.png', dpi=220)
    plt.close()

# 1 prediction quality / decision sensitivity
s25 = json.load(open(ROOT/'STEP25_PREDICTION_DECISION_REPORT.json'))['payload']
horizons = ['250ms','1s','5s']
base=[]; unc=[]; cal=[]
for h in horizons:
    m=s25['prediction_analysis'][h]['metrics']
    base.append(m['training_base_rate']['log_loss'])
    unc.append(m['uncalibrated_model']['log_loss'])
    cal.append(m['calibrated_model']['log_loss'])
x=np.arange(len(horizons)); w=.25
fig,ax=plt.subplots(figsize=(5.8,3.0))
ax.bar(x-w,base,w,label='Training base rate')
ax.bar(x,unc,w,label='Uncalibrated temporal')
ax.bar(x+w,cal,w,label='Calibrated temporal')
ax.set_xticks(x,horizons); ax.set_ylabel('Engineering-holdout log loss')
ax.set_title('Predictive quality across candidate horizons')
ax.legend(frameon=False,ncol=3,loc='upper left')
ax.grid(axis='y',alpha=.25)
save('prediction_logloss')

# 2 relationship counts
rel=s25['engineering_summary']['relationship_counts']
labels=['Pred. improved\nDecision unchanged','Pred. improved\nDecision changed','Pred. not improved\nDecision unchanged','Pred. not improved\nDecision changed']
vals=[rel['prediction_improved_decision_unchanged'],rel['prediction_improved_decision_changed'],rel['prediction_not_improved_decision_unchanged'],rel['prediction_not_improved_decision_changed']]
fig,ax=plt.subplots(figsize=(5.5,3.0))
ax.bar(np.arange(4),vals)
ax.set_xticks(np.arange(4),labels); ax.set_ylabel('Comparison-weight cases')
ax.set_title('Prediction quality and downstream decision response are not monotone')
ax.grid(axis='y',alpha=.25)
for i,v in enumerate(vals): ax.text(i,v+2,str(v),ha='center',va='bottom',fontsize=8)
save('prediction_decision_relationships')

# 3 imitation OOD
s26=json.load(open(ROOT/'STEP26_IMITATION_REPORT.json'))
metrics=['Action agreement','p95 shortfall\n(bps)']
raw=[s26['evaluation']['ood']['student_raw']['final_action_agreement']*100,s26['evaluation']['ood']['student_raw']['p95_shortfall_bps']]
fb=[s26['evaluation']['ood']['student_with_teacher_fallback']['final_action_agreement']*100,s26['evaluation']['ood']['student_with_teacher_fallback']['p95_shortfall_bps']]
teacher=[100,s26['evaluation']['ood']['teacher']['p95_shortfall_bps']]
# normalize split into two panels to avoid mixed units
fig,axs=plt.subplots(1,2,figsize=(6.2,2.7))
axs[0].bar(['Raw student','Student + fallback'],[raw[0],fb[0]])
axs[0].axhline(100,linestyle='--',linewidth=.8,label='Teacher reference')
axs[0].set_ylim(0,105); axs[0].set_ylabel('Teacher-action agreement (%)'); axs[0].set_title('OOD imitation fidelity'); axs[0].grid(axis='y',alpha=.25)
axs[1].bar(['Teacher','Raw student','Student + fallback'],[teacher[1],raw[1],fb[1]])
axs[1].set_ylabel('p95 implementation shortfall (bps)'); axs[1].set_title('OOD tail execution cost'); axs[1].grid(axis='y',alpha=.25)
for a in axs: a.tick_params(axis='x',rotation=20)
plt.tight_layout(); plt.savefig(OUT/'imitation_ood.pdf'); plt.savefig(OUT/'imitation_ood.png',dpi=220,bbox_inches='tight'); plt.close()

# 4 RL mean + CVaR ID/OOD
s27=json.load(open(ROOT/'STEP27_RL_REPORT.json'))
policies=['PPO\n(5-seed mean)','Liquidity-aware','TWAP-like','Immediate']
id_mean=[s27['aggregate']['id_mean_cost_bps']['mean'], s27['baselines']['liquidity_aware']['id']['mean_cost_bps'], s27['baselines']['twap_like']['id']['mean_cost_bps'], s27['baselines']['immediate']['id']['mean_cost_bps']]
ood_mean=[s27['aggregate']['ood_mean_cost_bps']['mean'], s27['baselines']['liquidity_aware']['ood']['mean_cost_bps'], s27['baselines']['twap_like']['ood']['mean_cost_bps'], s27['baselines']['immediate']['ood']['mean_cost_bps']]
id_cvar=[s27['aggregate']['id_cvar95_cost_bps']['mean'], s27['baselines']['liquidity_aware']['id']['cvar95_cost_bps'], s27['baselines']['twap_like']['id']['cvar95_cost_bps'], s27['baselines']['immediate']['id']['cvar95_cost_bps']]
ood_cvar=[s27['aggregate']['ood_cvar95_cost_bps']['mean'], s27['baselines']['liquidity_aware']['ood']['cvar95_cost_bps'], s27['baselines']['twap_like']['ood']['cvar95_cost_bps'], s27['baselines']['immediate']['ood']['cvar95_cost_bps']]
fig,axs=plt.subplots(1,2,figsize=(6.5,2.9))
x=np.arange(4); w=.36
axs[0].bar(x-w/2,id_mean,w,label='ID'); axs[0].bar(x+w/2,ood_mean,w,label='OOD')
axs[0].set_xticks(x,policies); axs[0].set_ylabel('Mean cost (bps)'); axs[0].set_title('Mean execution cost'); axs[0].legend(frameon=False); axs[0].grid(axis='y',alpha=.25)
axs[1].bar(x-w/2,id_cvar,w,label='ID'); axs[1].bar(x+w/2,ood_cvar,w,label='OOD')
axs[1].set_xticks(x,policies); axs[1].set_ylabel('CVaR95 cost (bps)'); axs[1].set_title('Tail execution cost'); axs[1].grid(axis='y',alpha=.25)
for a in axs: a.tick_params(axis='x',rotation=20)
plt.tight_layout(); plt.savefig(OUT/'rl_id_ood.pdf'); plt.savefig(OUT/'rl_id_ood.png',dpi=220,bbox_inches='tight'); plt.close()

# 5 robustness winners and central reference
s28=json.load(open(ROOT/'STEP28_ROBUSTNESS_REPORT.json'))
wins=s28['ranking_summary']['win_counts']
order=['liquidity_aware','ppo_aggregate','twap_like','immediate']
pretty=['Liquidity-aware','PPO aggregate','TWAP-like','Immediate']
fig,axs=plt.subplots(1,2,figsize=(6.5,2.9))
axs[0].bar(pretty,[wins[o] for o in order]); axs[0].set_ylabel('Stress cells ranked first'); axs[0].set_title('First-place frequency over 43 stress cells'); axs[0].tick_params(axis='x',rotation=20); axs[0].grid(axis='y',alpha=.25)
# Aggregate PPO point mean is stored in the ranking artifact; individual seeds live in Step 28.
s29_for_central=json.load(open(ROOT/'STEP29_STATISTICS_REPORT.json'))
central=s29_for_central['ranking_stability']['central_reference']['point_mean_cost_bps']
vals=[central[o] for o in order]
axs[1].bar(pretty,vals); axs[1].set_ylabel('Mean cost (bps)'); axs[1].set_title('Central controlled regime'); axs[1].tick_params(axis='x',rotation=20); axs[1].grid(axis='y',alpha=.25)
plt.tight_layout(); plt.savefig(OUT/'robustness_summary.pdf'); plt.savefig(OUT/'robustness_summary.png',dpi=220,bbox_inches='tight'); plt.close()

# 6 ranking stability probabilities: central + selected fragile cases
s29=json.load(open(ROOT/'STEP29_STATISTICS_REPORT.json'))
case_names=['central_reference','size_25pct_depth','spread_narrow','simulator_mismatch_adverse','size_10pct_depth','horizon_30s_proxy']
# fallback mapping if exact mismatch names
avail=s29['ranking_stability']
case_names=[c for c in case_names if c in avail]
labels=[]; probs=[]
for c in case_names:
    r=avail[c]
    labels.append(c.replace('_',' '))
    probs.append(100*r['point_winner_bootstrap_probability'])
fig,ax=plt.subplots(figsize=(6.1,3.1))
ax.barh(np.arange(len(labels)),probs)
ax.axvline(80,linestyle='--',linewidth=.8,label='80% stability threshold')
ax.set_yticks(np.arange(len(labels)),labels); ax.set_xlabel('Bootstrap probability point winner remains best (%)'); ax.set_xlim(0,100); ax.set_title('Selected ranking-stability diagnostics'); ax.legend(frameon=False); ax.grid(axis='x',alpha=.25)
save('ranking_stability_selected')

# 7 C++ matching scaling
s30=json.load(open(ROOT/'STEP30_PERFORMANCE_REPORT.json'))
threads=[1,2,4]
base_tp=[s30['cpp_matching'][str(t)]['baseline']['throughput_ops_per_second']/1e6 for t in threads]
opt_tp=[s30['cpp_matching'][str(t)]['optimized']['throughput_ops_per_second']/1e6 for t in threads]
fig,ax=plt.subplots(figsize=(5.3,3.0))
ax.plot(threads,base_tp,marker='o',label='Baseline')
ax.plot(threads,opt_tp,marker='o',label='Capacity-hint optimization')
ax.set_xticks(threads); ax.set_xlabel('Independent engine threads'); ax.set_ylabel('Throughput (million ops/s)'); ax.set_title('C++ matching-engine CPU scaling'); ax.legend(frameon=False); ax.grid(alpha=.25)
save('cpp_scaling')

# 8 CUDA batch-one and temporal scaling
cuda=json.load(open(ROOT/'STEP30_CUDA_GATE.json'))
models=['imitation','ppo_seed_27','temporal_5s']; names=['Imitation','PPO','Temporal 5 s']
cpu=[cuda['models'][m]['1']['cpu']['median_ns']/1000 for m in models]
gpu=[cuda['models'][m]['1']['gpu_transfer_inclusive']['median_ns']/1000 for m in models]
fig,axs=plt.subplots(1,2,figsize=(6.5,2.9))
x=np.arange(3); w=.36
axs[0].bar(x-w/2,cpu,w,label='CPU'); axs[0].bar(x+w/2,gpu,w,label='T4 incl. transfers')
axs[0].set_xticks(x,names); axs[0].set_ylabel('Median latency (µs)'); axs[0].set_title('Batch-one decision latency'); axs[0].legend(frameon=False); axs[0].grid(axis='y',alpha=.25)
bs=[1,32,256]
tcpu=[cuda['models']['temporal_5s'][str(b)]['cpu']['median_ns']/1000 for b in bs]
tgpu=[cuda['models']['temporal_5s'][str(b)]['gpu_transfer_inclusive']['median_ns']/1000 for b in bs]
axs[1].plot(bs,tcpu,marker='o',label='CPU'); axs[1].plot(bs,tgpu,marker='o',label='T4 incl. transfers')
axs[1].set_xscale('log',base=2); axs[1].set_xticks(bs,bs); axs[1].set_xlabel('Batch size'); axs[1].set_ylabel('Median latency (µs)'); axs[1].set_title('Temporal-model scaling'); axs[1].legend(frameon=False); axs[1].grid(alpha=.25)
plt.tight_layout(); plt.savefig(OUT/'cuda_performance.pdf'); plt.savefig(OUT/'cuda_performance.png',dpi=220,bbox_inches='tight'); plt.close()

print('generated', len(list(OUT.glob('*.pdf'))), 'PDF figures')
