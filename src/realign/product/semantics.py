"""Product wording does not change approved scientific outcome identifiers."""
LABELS={'KEEP_UNCHANGED':'Keep nominal model','CALIBRATE_PARAMETERS':'Recalibrate parameters',
        'CORRECT_MEASUREMENT':'Measurement correction required',
        'REPAIR_STRUCTURE':'Select predefined peg model','ABSTAIN':'Abstain — evidence insufficient'}
EXPLANATIONS={
    'KEEP_UNCHANGED':'Predictively adequate inside the tested operating envelope; an inactive mechanism is not excluded.',
    'CALIBRATE_PARAMETERS':'A parameter revision explains the discrepancy within the existing free model.',
    'CORRECT_MEASUREMENT':'A reference check found unresolved measurement quality. Correction and independent verification are still required.',
    'REPAIR_STRUCTURE':'The existing peg-contact dynamics are selected for prediction within the tested envelope. This is not unique causal identification or equation discovery.',
    'ABSTAIN':'The available evidence or execution does not support an accepted predictive revision.'}


def decision_view(freeze):
    outcome=freeze['outcome']
    if outcome not in LABELS:
        raise ValueError('unknown decision outcome')
    explanation=EXPLANATIONS[outcome]
    if outcome=='ABSTAIN' and 'API_ERROR' in freeze.get('reasons',[]):
        explanation='The model/API protocol stopped before an accepted scientific conclusion. This recorded attempt is not a successful investigation.'
    elif outcome=='ABSTAIN' and 'BUDGET' in freeze.get('reasons',[]):
        explanation='The declared investigation budget was reached; no predictive revision was accepted.'
    return {'outcome':outcome,'label':LABELS[outcome],'explanation':explanation,'reasons':freeze.get('reasons',[]),
        'correction_applied':False,'correction_verified':False,
        'accepted':freeze['proposal_accepted'],'model_ref':freeze['model_ref'],
        'freeze_sha256':freeze['freeze_sha256'],'scope':freeze['scope']}
