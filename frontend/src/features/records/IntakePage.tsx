import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FileText, LoaderCircle, Plus, RefreshCw, Send, ShieldCheck, Trash2, Upload, X } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  confirmIntakeReview,
  discardIntakeReview,
  extractPermittedIntake,
  getDocumentSourceUrl,
  getIntakeReviews,
  handoffIntakeReview,
  listMoittOrganisations,
  listMoittProjects,
  setIntakeCloudPermission,
  updateIntakeReview,
  uploadForIntake,
  type IntakeCommitment,
  type IntakeItem,
  type IntakePayload,
} from '../../lib/api'
import './intake.css'

export default function IntakePage({ userRole }: { userRole: string }) {
  const client = useQueryClient()
  const location = useLocation()
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [payload, setPayload] = useState<IntakePayload | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [classification, setClassification] = useState('internal')
  const [sourceUrl, setSourceUrl] = useState('')
  const [evidence, setEvidence] = useState<{ quote: string; page: number | null } | null>(null)
  const [createOrganisations, setCreateOrganisations] = useState<string[]>([])
  const [createProjects, setCreateProjects] = useState<string[]>([])
  const [notice, setNotice] = useState('')
  const reviews = useQuery({ queryKey: ['intake-reviews'], queryFn: getIntakeReviews })
  const organisations = useQuery({ queryKey: ['moitt-organisations'], queryFn: listMoittOrganisations })
  const projects = useQuery({ queryKey: ['moitt-projects'], queryFn: listMoittProjects })
  const selected = reviews.data?.find(item => item.id === selectedId) ?? null

  useEffect(() => {
    const dropped = (location.state as { intakeFile?: File } | null)?.intakeFile
    if (dropped instanceof File) {
      setFile(dropped)
      setNotice(`Ready to upload ${dropped.name}.`)
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [location.pathname, location.state, navigate])

  const upload = useMutation({
    mutationFn: () => file ? uploadForIntake(file, classification) : Promise.reject(new Error('Choose a document first.')),
    onSuccess: async result => {
      setNotice(result.duplicate ? 'This file was already uploaded. Opened the existing review.' : 'Upload received. Check the extracted details before confirming.')
      setSelectedId(result.id)
      setPayload(result.payload)
      setFile(null)
      await client.invalidateQueries({ queryKey: ['intake-reviews'] })
    },
  })
  const save = useMutation({
    mutationFn: () => selectedId && payload
      ? updateIntakeReview(selectedId, payload, createOrganisations, createProjects)
      : Promise.reject(new Error('Select an intake review.')),
    onSuccess: async result => {
      setPayload(result.payload)
      setCreateOrganisations([])
      setCreateProjects([])
      setNotice('Review changes saved and evidence rechecked.')
      await Promise.all([
        client.invalidateQueries({ queryKey: ['intake-reviews'] }),
        client.invalidateQueries({ queryKey: ['moitt-projects'] }),
        client.invalidateQueries({ queryKey: ['moitt-organisations'] }),
      ])
    },
  })
  const confirm = useMutation({
    mutationFn: async () => {
      if (!selectedId || !payload) throw new Error('Select an intake review.')
      await updateIntakeReview(selectedId, payload, createOrganisations, createProjects)
      return confirmIntakeReview(selectedId)
    },
    onSuccess: async result => {
      setNotice(result.diff_summary ?? 'Document confirmed and added.')
      setSelectedId(null)
      setPayload(null)
      setCreateOrganisations([])
      setCreateProjects([])
      await Promise.all([
        client.invalidateQueries({ queryKey: ['intake-reviews'] }),
        client.invalidateQueries({ queryKey: ['dashboard'] }),
        client.invalidateQueries({ queryKey: ['moitt-projects'] }),
        client.invalidateQueries({ queryKey: ['moitt-actions'] }),
      ])
    },
  })
  const handoff = useMutation({
    mutationFn: () => selectedId ? handoffIntakeReview(selectedId) : Promise.reject(new Error('Select an intake review.')),
    onSuccess: async () => {
      setNotice('Review sent to the Chief of Staff.')
      await client.invalidateQueries({ queryKey: ['intake-reviews'] })
    },
  })
  const discard = useMutation({
    mutationFn: () => selectedId ? discardIntakeReview(selectedId) : Promise.reject(new Error('Select an intake review.')),
    onSuccess: async () => {
      setNotice('Upload discarded.')
      setSelectedId(null)
      setPayload(null)
      await client.invalidateQueries({ queryKey: ['intake-reviews'] })
    },
  })
  const cloudExtract = useMutation({
    mutationFn: async () => {
      if (!selectedId) throw new Error('Select a review.')
      await setIntakeCloudPermission(selectedId, true)
      return extractPermittedIntake(selectedId)
    },
    onSuccess: async result => {
      setSelectedId(result.id)
      setPayload(result.payload)
      setNotice('Administrator permission recorded. Extraction is ready for review.')
      await client.invalidateQueries({ queryKey: ['intake-reviews'] })
    },
  })
  useEffect(() => {
    if (selected && payload === null) setPayload(selected.payload)
  }, [selected, payload])
  useEffect(() => {
    let alive = true
    setSourceUrl('')
    setEvidence(null)
    if (selected) {
      getDocumentSourceUrl(selected.document_id)
        .then(url => { if (alive) setSourceUrl(url); else URL.revokeObjectURL(url) })
        .catch(() => { if (alive) setSourceUrl('') })
    }
    return () => { alive = false }
  }, [selected?.document_id])
  useEffect(() => () => { if (sourceUrl) URL.revokeObjectURL(sourceUrl) }, [sourceUrl])

  const allClear = useMemo(() => Boolean(payload)
    && (payload?.doc_kind !== 'minutes' || Boolean(payload.meeting_date))
    && (payload?.doc_kind === 'minutes' || Boolean(payload?.project_hint))
    && (payload?.actions ?? []).every(row => row.quote_verified && !row.needs_input)
    && (payload?.commitments ?? []).every(row => row.quote_verified && !row.needs_input)
    && (payload?.decisions ?? []).every(row => row.quote_verified), [payload])
  const busy = upload.isPending || save.isPending || confirm.isPending || handoff.isPending || cloudExtract.isPending || discard.isPending
  const error = upload.error ?? save.error ?? confirm.error ?? handoff.error ?? cloudExtract.error ?? discard.error

  function pickFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null)
    setNotice('')
  }
  function update<K extends keyof IntakePayload>(key: K, value: IntakePayload[K]) {
    setPayload(current => current ? { ...current, [key]: value } : current)
  }
  function patchAction<K extends keyof IntakeItem>(index: number, key: K, value: IntakeItem[K]) {
    setPayload(current => current ? { ...current, actions: current.actions.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value, needs_input: true } : row) } : current)
  }
  function patchCommitment<K extends keyof IntakeCommitment>(index: number, key: K, value: IntakeCommitment[K]) {
    setPayload(current => current ? { ...current, commitments: current.commitments.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value, needs_input: true } : row) } : current)
  }
  function addToList(setter: (value: string[]) => void, values: string[], name: string) {
    const clean = name.trim()
    if (clean && !values.some(item => item.toLocaleLowerCase() === clean.toLocaleLowerCase())) setter([...values, clean])
  }
  function isKnownOrganisation(name: string | null) {
    return Boolean(name && organisations.data?.some(item => item.name.toLocaleLowerCase() === name.toLocaleLowerCase() || item.short_name.toLocaleLowerCase() === name.toLocaleLowerCase() || item.aliases.some(alias => alias.toLocaleLowerCase() === name.toLocaleLowerCase())))
  }
  function isKnownProject(name: string | null) {
    return Boolean(name && projects.data?.some(item => item.name.toLocaleLowerCase() === name.toLocaleLowerCase() || item.code.toLocaleLowerCase() === name.toLocaleLowerCase() || item.aliases.some(alias => alias.toLocaleLowerCase() === name.toLocaleLowerCase())))
  }

  return <section className="intake-page">
    <header className="intake-heading">
      <div><span className="eyebrow">DOCUMENT INTAKE</span><h1>Add minutes or a document</h1><p>Review the source and extracted details before they reach the Minister’s dashboard.</p></div>
      <div className="intake-security"><ShieldCheck size={16}/> Human confirmation required</div>
    </header>

    {userRole !== 'admin' && <div className="intake-upload-card">
      <div className="intake-upload-copy"><div className="intake-upload-icon"><Upload size={20}/></div><div><h2>Upload a ministry document</h2><p>PDF, DOCX, TXT, MD or image · up to 30 MB</p></div></div>
      <div className="intake-upload-form">
        <label className="intake-file"><FileText size={16}/><span>{file?.name ?? 'Choose a file'}</span><input type="file" accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.tif,.tiff,.webp" onChange={pickFile}/></label>
        <label className="intake-select">Classification<select value={classification} onChange={event => setClassification(event.target.value)}><option value="public">Public</option><option value="internal">Internal</option><option value="confidential">Confidential</option></select></label>
        <button className="primary-button" disabled={!file || busy} onClick={() => upload.mutate()}>{upload.isPending ? <LoaderCircle className="spin" size={16}/> : <Upload size={16}/>} Upload and extract</button>
      </div>
    </div>}

    {(notice || error) && <div className={`intake-notice ${error ? 'error' : ''}`} role={error ? 'alert' : 'status'}>{error?.message ?? notice}<button className="icon-button" onClick={() => { setNotice(''); upload.reset(); save.reset(); confirm.reset(); handoff.reset(); cloudExtract.reset(); discard.reset() }} aria-label="Dismiss"><X size={15}/></button></div>}

    <div className="intake-workspace">
      <aside className="intake-queue card">
        <div className="intake-card-head"><div><span className="eyebrow">REVIEW INBOX</span><h2>Awaiting confirmation</h2></div><button className="icon-button" aria-label="Refresh reviews" onClick={() => void reviews.refetch()}><RefreshCw size={15}/></button></div>
        {reviews.isPending ? <div className="intake-empty">Loading reviews…</div> : reviews.isError ? <div className="intake-empty">{reviews.error.message}</div> : reviews.data.length === 0 ? <div className="intake-empty"><FileText size={24}/><b>No documents waiting</b><span>Uploads assigned to you will appear here.</span></div> : <div className="intake-queue-list">{reviews.data.map(row => <button key={row.id} className={`intake-queue-row ${selectedId === row.id ? 'selected' : ''}`} onClick={() => { setSelectedId(row.id); setPayload(row.payload); setCreateOrganisations([]); setCreateProjects([]) }}><span className="intake-file-mark"><FileText size={17}/></span><span className="intake-queue-text"><b>{row.payload.title}</b><small>{row.doc_kind} · {row.payload.actions.length} actions · {row.payload.commitments.length} commitments</small><small>{row.status === 'awaiting_permission' ? 'Waiting for administrator permission' : row.warnings.length ? `${row.warnings.length} items need review` : 'Ready for review'}</small></span></button>)}</div>}
      </aside>

      <div className="intake-review-area">
        {!selected || !payload ? <div className="intake-empty intake-empty-large"><FileText size={32}/><b>Select a document to review</b><span>The original source and extracted details appear side by side.</span></div> : <>
          <div className="intake-review-title">
            <div><span className="eyebrow">{payload.doc_kind.toUpperCase()} REVIEW</span><h2>{payload.title}</h2><p>{payload.summary || 'Review the extracted details against the original document.'}</p></div>
            <div className="intake-review-actions">
              {selected.status === 'awaiting_permission' && userRole === 'admin' && <button className="primary-button" disabled={busy} onClick={() => cloudExtract.mutate()}><ShieldCheck size={15}/> Allow cloud extraction</button>}
              {userRole !== 'admin' && selected.status !== 'confirmed' && <>
                <button className="outline-button danger-outline" disabled={busy} onClick={() => { if (window.confirm('Discard this upload and its pending review?')) discard.mutate() }}><Trash2 size={15}/> Discard</button>
                <button className="outline-button" disabled={busy} onClick={() => handoff.mutate()}><Send size={15}/> Send to Chief of Staff</button>
                {selected.status === 'review' && <><button className="outline-button" disabled={busy} onClick={() => save.mutate()}><Check size={15}/> Save review</button><button className="primary-button" disabled={!allClear || busy} title={!allClear ? 'Resolve flagged fields and verify source quotes first' : ''} onClick={() => confirm.mutate()}>{confirm.isPending ? <LoaderCircle className="spin" size={15}/> : <Check size={15}/>} Confirm and add</button></>}
              </>}
            </div>
          </div>
          {selected.warnings.length > 0 && <div className="intake-warning">{selected.warnings.map((item, index) => <span key={`${index}-${item}`}>{item}</span>)}</div>}

          <div className="intake-two-pane">
            <section className="intake-source card">
              <div className="intake-card-head"><div><span className="eyebrow">SOURCE DOCUMENT</span><h3>Original</h3></div><a className="text-link" href={sourceUrl || undefined} target="_blank" rel="noreferrer">Open separately ↗</a></div>
              {sourceUrl ? <iframe title="Uploaded source document" src={evidence?.page ? `${sourceUrl}#page=${evidence.page}` : sourceUrl} /> : <div className="intake-empty">Preparing source preview…</div>}
              {evidence && <div className="intake-evidence-highlight"><span>Selected source quote{evidence.page ? ` · page ${evidence.page}` : ''}</span><mark>{evidence.quote}</mark></div>}
            </section>

            <section className="intake-extracted card">
              <div className="intake-card-head"><div><span className="eyebrow">AI EXTRACTED · HUMAN REVIEW</span><h3>{payload.doc_kind === 'minutes' ? 'Meeting and actions' : 'Document and follow-up'}</h3></div><span className="intake-count">{payload.actions.length} actions</span></div>
              <datalist id="intake-organisations">{organisations.data?.map(item => <option key={item.id} value={item.name}/>)}</datalist>
              <datalist id="intake-projects">{projects.data?.map(item => <option key={item.id} value={item.name}/>)}</datalist>

              <div className="intake-fields">
                <label>Document title<input value={payload.title} onChange={event => update('title', event.target.value)}/></label>
                <label>Document type<select value={payload.doc_kind} onChange={event => update('doc_kind', event.target.value as IntakePayload['doc_kind'])}><option value="minutes">Minutes</option><option value="letter">Letter</option><option value="brief">Brief</option><option value="note">Note</option><option value="other">Other</option></select></label>
                <label>{payload.doc_kind === 'minutes' ? 'Meeting date' : 'Document date'}<input type="date" value={payload.meeting_date ?? ''} onChange={event => update('meeting_date', event.target.value || null)}/></label>
                {payload.doc_kind === 'minutes' && <>
                  <label>Meeting time<input type="time" value={payload.meeting_time ?? ''} onChange={event => update('meeting_time', event.target.value || null)}/></label>
                  <label>Chair<input value={payload.chair ?? ''} onChange={event => update('chair', event.target.value || null)}/></label>
                  <label>Venue<input value={payload.venue ?? ''} onChange={event => update('venue', event.target.value || null)}/></label>
                  <label>Participants and organisation hints<textarea rows={2} value={payload.participants.map(item => item.org_hint ? `${item.text} — ${item.org_hint}` : item.text).join(', ')} onChange={event => update('participants', event.target.value.split(',').map(item => { const [text, org_hint] = item.split('—').map(part => part.trim()); return text ? { text, org_hint: org_hint || null } : null }).filter((item): item is NonNullable<typeof item> => item !== null))}/></label>
                </>}
                <label>Project for this document<input list="intake-projects" value={payload.project_hint ?? ''} onChange={event => update('project_hint', event.target.value || null)}/></label>
              </div>
              {payload.project_hint && !isKnownProject(payload.project_hint) && <button className="create-entity-button" onClick={() => addToList(setCreateProjects, createProjects, payload.project_hint ?? '')}><Plus size={13}/>{createProjects.includes(payload.project_hint) ? 'Project will be created on save' : `Create project “${payload.project_hint}”`}</button>}
              {payload.summary && <label className="intake-summary-field">Three-sentence summary<textarea rows={3} value={payload.summary} onChange={event => update('summary', event.target.value)}/></label>}

              {payload.actions.map((row, index) => <article className={`intake-item ${row.needs_input || !row.quote_verified ? 'needs-review' : ''}`} key={`action-${index}`} onClick={() => setEvidence({ quote: row.source_quote, page: row.source_page })}>
                <div className="intake-item-top"><b>Action {index + 1}</b><span className={row.quote_verified ? 'verified' : 'unverified'}>{row.quote_verified ? 'Source verified' : 'Quote not verified'} · {Math.round(row.confidence * 100)}% confidence</span></div>
                <label>Description<textarea rows={2} value={row.description} onChange={event => patchAction(index, 'description', event.target.value)}/></label>
                <div className="intake-fields">
                  <label>Owner organisation<input list="intake-organisations" value={row.owner_org ?? ''} onChange={event => patchAction(index, 'owner_org', event.target.value || null)}/></label>
                  <label>Responsible person<input value={row.owner_person ?? ''} onChange={event => patchAction(index, 'owner_person', event.target.value || null)}/></label>
                  <label>Deadline as written<input value={row.deadline_text} onChange={event => patchAction(index, 'deadline_text', event.target.value)}/><small>{row.resolved_deadline ? `Resolves to ${new Date(`${row.resolved_deadline}T00:00:00`).toLocaleDateString('en-GB')} (${row.deadline_precision})` : 'Date needs review'}</small></label>
                  <label>Project<input list="intake-projects" value={row.project ?? ''} onChange={event => patchAction(index, 'project', event.target.value || null)}/></label>
                  <label>Priority<select value={row.priority} onChange={event => patchAction(index, 'priority', event.target.value as IntakeItem['priority'])}><option value="A">A · Critical</option><option value="B">B · High</option><option value="C">C · Normal</option></select></label>
                  <label>Status at upload<select value={row.status_source} onChange={event => patchAction(index, 'status_source', event.target.value as IntakeItem['status_source'])}><option value="open">Open</option><option value="done_at_upload">Already done</option></select></label>
                </div>
                {row.owner_org && !isKnownOrganisation(row.owner_org) && <button className="create-entity-button" onClick={event => { event.stopPropagation(); addToList(setCreateOrganisations, createOrganisations, row.owner_org ?? '') }}><Plus size={13}/>{createOrganisations.includes(row.owner_org) ? 'Organisation will be created on save' : `Create organisation “${row.owner_org}”`}</button>}
                {row.project && !isKnownProject(row.project) && <button className="create-entity-button" onClick={event => { event.stopPropagation(); addToList(setCreateProjects, createProjects, row.project ?? '') }}><Plus size={13}/>{createProjects.includes(row.project) ? 'Project will be created on save' : `Create project “${row.project}”`}</button>}
                <label>Source quote · correct it against the original<textarea rows={2} value={row.source_quote} onChange={event => patchAction(index, 'source_quote', event.target.value)}/></label>
              </article>)}

              {payload.commitments.map((row, index) => <article className={`intake-item ${row.needs_input || !row.quote_verified ? 'needs-review' : ''}`} key={`commitment-${index}`} onClick={() => setEvidence({ quote: row.source_quote, page: row.source_page })}>
                <div className="intake-item-top"><b>Commitment {index + 1}</b><span className={row.quote_verified ? 'verified' : 'unverified'}>{row.quote_verified ? 'Source verified' : 'Quote not verified'} · {Math.round(row.confidence * 100)}% confidence</span></div>
                <label>Commitment<textarea rows={2} value={row.statement} onChange={event => patchCommitment(index, 'statement', event.target.value)}/></label>
                <div className="intake-fields">
                  <label>Project<input list="intake-projects" value={row.project ?? ''} onChange={event => patchCommitment(index, 'project', event.target.value || null)}/></label>
                  <label>Due as written<input value={row.due_text} onChange={event => patchCommitment(index, 'due_text', event.target.value)}/><small>{row.resolved_due_date ? `Resolves to ${new Date(`${row.resolved_due_date}T00:00:00`).toLocaleDateString('en-GB')} (${row.deadline_precision})` : 'Date needs review'}</small></label>
                  <label>Committed by<input list="intake-organisations" value={row.committed_by_org ?? row.committed_by_text ?? ''} onChange={event => patchCommitment(index, 'committed_by_org', event.target.value || null)}/></label>
                </div>
                {row.project && !isKnownProject(row.project) && <button className="create-entity-button" onClick={event => { event.stopPropagation(); addToList(setCreateProjects, createProjects, row.project ?? '') }}><Plus size={13}/>{createProjects.includes(row.project) ? 'Project will be created on save' : `Create project “${row.project}”`}</button>}
                <label>Source quote · correct it against the original<textarea rows={2} value={row.source_quote} onChange={event => patchCommitment(index, 'source_quote', event.target.value)}/></label>
              </article>)}

              {payload.decisions.map((row, index) => <article className={`intake-item ${!row.quote_verified ? 'needs-review' : ''}`} key={`decision-${index}`} onClick={() => setEvidence({ quote: row.source_quote, page: row.source_page })}>
                <div className="intake-item-top"><b>Decision {index + 1}</b><span className={row.quote_verified ? 'verified' : 'unverified'}>{row.quote_verified ? 'Source verified' : 'Quote not verified'}</span></div>
                <label>Decision<textarea rows={2} value={row.text} onChange={event => setPayload(current => current ? { ...current, decisions: current.decisions.map((item, itemIndex) => itemIndex === index ? { ...item, text: event.target.value } : item) } : current)}/></label>
                <label>Source quote<textarea rows={2} value={row.source_quote} onChange={event => setPayload(current => current ? { ...current, decisions: current.decisions.map((item, itemIndex) => itemIndex === index ? { ...item, source_quote: event.target.value } : item) } : current)}/></label>
              </article>)}

              <div className="intake-review-footer"><span>{allClear ? 'Ready: confirmation will add the records shown above.' : 'Resolve highlighted fields and verify the source quotes before confirming.'}</span><button className="outline-button" disabled={busy} onClick={() => { setSelectedId(null); setPayload(null) }}>Close review</button></div>
            </section>
          </div>
        </>}
      </div>
    </div>
  </section>
}
