const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type DemoUser = { id: string; name: string; email: string; role: string; designation: string; active: boolean }
export type Job = { id:string; resource_type:string; resource_id:string; status:'queued'|'running'|'succeeded'|'failed'|'cancelled'; progress:number; message:string; error_message:string|null; created_at:string; started_at:string|null; finished_at:string|null; updated_at:string }
export type HealthStatus = { status: string; database: string; environment: string; ai_zone: 'cloud' | 'local' }
export type Officer = { id: string; name: string; designation: string; role: string }
export type RegisterEntry = {
  id: string; serial_no: number | null; fy: string; occurred_at: string; occasion_type: string; occasion_ref: string | null;
  description: string; minister_words: string | null; officer_id: string; officer: Pick<Officer, 'id' | 'name' | 'designation'>;
  deadline: string; priority: 'A' | 'B' | 'C'; source_record: string | null; status: 'open' | 'in_progress' | 'closed' | 'closed_with_note';
  closed_at: string | null; closure_note: string | null; transaction_id: string | null; origin: 'manual' | 'ai_proposed';
  review_state: 'approved' | 'proposed' | 'rejected'; ai_assistance: Record<string, unknown> | null; evidence: Record<string, unknown> | null;
  created_at: string; updated_at: string; overdue: boolean;
}
export type AuditItem = { id: string; actor_id: string | null; actor_name: string | null; action: string; before: Record<string, unknown> | null; after: Record<string, unknown> | null; ip: string | null; at: string }
export type RegisterPage = { items: RegisterEntry[]; total: number; limit: number; offset: number }
export type StageCount = { stage: string; label: string; count: number }
export type DashboardSummary = {
  week_starting: string; week_ending: string;
  kpis: { transactions_in_process: number; decisions_due_this_week: number; actions_overdue: number; engagements_this_week: number };
  transactions_by_stage: StageCount[];
  next_milestones: Array<{ id: string; code: string; name: string; sector: string; stage: string; next_milestone: string; next_milestone_date: string; health: string }>;
  decisions_due: Array<{ id: string; title: string; due_date: string; status: string; context_ref: string | null; transaction_id: string | null; transaction_code: string | null }>;
  overdue_actions: Array<{ id: string; serial_no: number; fy: string; description: string; officer_id: string; officer_name: string; deadline: string; priority: string; status: string; overdue: boolean }>;
  upcoming_engagements: Array<{ id: string; title: string; engagement_type: string; starts_at: string; location: string; pack_status: string; pack_due_at: string; pack_at_risk: boolean; owner_id: string; owner_name: string; transaction_id: string | null; transaction_code: string | null }>;
  last_refreshed: string; source_note: string;
  moitt?: {active_projects:number;open_actions:number;overdue_actions:number;open_commitments:number;awaiting_confirmation:number;projects:Array<{id:string;code:string;name:string;health:string;stage:string;summary:string}>}
}
export type DrillRecord = { record_type: string; id: string; label: string; code?: string; due_date?: string; deadline?: string; starts_at?: string; officer?: string }
export type DrillResult = { kpi: string; week_starting: string; week_ending: string; total: number; records: DrillRecord[] }
export type Transaction = { id: string; code: string; name: string; sector: string; stage: string; next_milestone: string; next_milestone_date: string; health: 'on_track' | 'at_risk' | 'delayed'; lead_user_id: string; lead_user: Pick<Officer, 'id' | 'name' | 'designation'>; summary: string; updated_by: string; updated_at: string }
export type TransactionEvent = { id: string; transaction_id: string; occurred_at: string; event_type: string; description: string; source_ref: string | null }
export type TransactionDetail = Transaction & { events: TransactionEvent[]; register_entries: Array<{ id: string; serial_no: number | null; fy: string; description: string; deadline: string; status: string; officer_id: string }> }
export type TransactionPage = { items: Transaction[]; total: number; limit: number; offset: number }
export type MinisterDecision = { id: string; title: string; due_date: string; transaction_id: string | null; status: string; context_ref: string | null; transaction: Transaction | null }
export type Engagement = { id: string; title: string; engagement_type: string; starts_at: string; location: string; pack_status: string; pack_due_at: string; owner_id: string; owner: Pick<Officer, 'id' | 'name' | 'designation'>; transaction_id: string | null; transaction: Transaction | null }
export type ToolSwitch = { tool: string; suspended: boolean; changed_by: string | null; changed_at: string; reason: string | null }
export type AIRun = { id: string; tool: string; model_role: string; model: string; zone: string; classification: string; is_synthetic: boolean; user_id: string | null; user_name: string | null; outcome: string; prompt_version: string; input_tokens: number | null; output_tokens: number | null; latency_ms: number | null; error_code: string | null; approver_id: string | null; approver_name: string | null; approved_at: string | null; diff_summary: string | null; created_at: string }
export type TranscriptSegment = { start: number; end: number; text: string; lang: string; speaker: string | null }
export type MeetingAction = { id: string; meeting_id: string; ai_run_id: string | null; register_entry_id: string | null; description: string; officer_hint: string | null; officer_id: string | null; officer_name: string | null; deadline_hint: string | null; deadline_date: string | null; priority_suggestion: string; transaction_hint: string | null; transaction_id: string | null; quote: string; transcript_start: number; transcript_end: number; confidence: number; review_state: string; review_reason: string | null }
export type MinutesDraft = { id: string; meeting_id: string; version: number; body_markdown: string; status: string; drafted_by_run_id: string | null; reviewed_by: string | null; issued_at: string | null; export_path: string | null; demo_cache_used: boolean }
export type Meeting = { id: string; title: string; occurred_at: string; occasion_type: string; location: string; attendees: Array<{name:string;role?:string}>; audio_url: string | null; language_hint: string; classification: string; is_synthetic: boolean; status: string; draft_due_at: string; issue_due_at: string; transcript: {id:string;meeting_id:string;language:string;segments:TranscriptSegment[];stt_provider:string;stt_model:string} | null; minutes: MinutesDraft | null; actions: MeetingAction[]; created_at: string; updated_at: string }
export type SearchCitation = { number: number; document_id: string; title: string; doc_type: string; page: number | null; section: string | null; snippet: string; chunk_id: string }
export type SearchAnswer = { query: string; answer: string; declined: boolean; citations: SearchCitation[] }
export type SearchDocument = { id: string; title: string; doc_type: string; classification: string; transaction_id: string | null; source_note: string | null; is_synthetic: boolean; ingest_status: string; created_at: string; chunk_count: number }
export type JarvisMessage = { id:string; role:'user'|'assistant'; content:string; tool_calls:Array<{tool:string}>|null; citations:Array<{type:string;id:string;label:string;detail:string}>|null; created_at:string }
export type JarvisSession = { id:string; title:string; created_at:string; updated_at:string; messages:JarvisMessage[] }
export type ComplianceItem = {id:string;category:string;title:string;due_date:string;owner_id:string;owner_name:string;status:string;reference:string|null;created_at:string;updated_at:string}
export type SpotCheck = {id:string;period:string;sample:Array<{run_id:string;tool:string;model:string;zone:string;classification:string;created_at:string;reviewed:boolean}>;reconciled_by:string|null;reconciler_name:string|null;findings:string|null;status:string;creator_id:string;creator_name:string;created_at:string;updated_at:string}
export type AdminUser = {id:string;name:string;email:string;role:string;designation:string;active:boolean;created_at:string}
export type SystemHealth = {database:string;environment:string;ai_zone:string;chat_provider_configured:boolean;embedding_provider_configured:boolean;stt_package_installed:boolean;chroma_directory_exists:boolean;configured_models:{chat:string|null;embedding:string|null;stt:string}}
export type IntakeItem = {description:string;owner_org:string|null;owner_person:string|null;deadline_text:string;resolved_deadline:string|null;deadline_precision:string;status_source:'open'|'done_at_upload';project:string|null;source_quote:string;source_page:number|null;quote_verified:boolean;needs_input:boolean}
export type IntakeCommitment = {statement:string;committed_by_org:string|null;committed_by_text:string|null;due_text:string;resolved_due_date:string|null;deadline_precision:string;project:string|null;source_quote:string;source_page:number|null;quote_verified:boolean;needs_input:boolean}
export type IntakePayload = {doc_kind:'minutes'|'letter'|'brief'|'note'|'other';title:string;meeting_date:string|null;chair:string|null;venue:string|null;participants:string[];project_hint:string|null;summary:string;actions:IntakeItem[];commitments:IntakeCommitment[]}
export type IntakeReview = {id:string;document_id:string;status:string;doc_kind:string;payload:IntakePayload;warnings:string[];diff_summary:string|null;duplicate:boolean}
export type MoittOrganisation = {id:string;name:string;short_name:string;type:string;aliases:string[]}
export type MoittProject = {id:string;code:string;name:string;aliases:string[];sector:string;stage:string;health:string;health_reason:string;lead_org_id:string|null;summary:string;updated_at:string}

export async function getHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API}/health`)
  if (!response.ok) throw new Error('Health status is unavailable.')
  return response.json() as Promise<HealthStatus>
}

export async function login(email: string, password: string): Promise<{ access_token: string }> {
  const response = await fetch(`${API}/api/v1/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) })
  if (!response.ok) throw new Error(response.status === 401 ? 'Email or password did not match.' : 'Sign-in service is unavailable. Check that the API is running.')
  return response.json() as Promise<{ access_token: string }>
}

export async function getMe(token: string): Promise<DemoUser> {
  const response = await fetch(`${API}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
  if (!response.ok) throw new Error('Your session expired. Sign in again.')
  return response.json() as Promise<DemoUser>
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('pc-access-token')
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API}${path}`, { ...init, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: { message?: string }; detail?: string } | null
    throw new Error(body?.error?.message ?? body?.detail ?? `Request failed (${response.status}).`)
  }
  return response.json() as Promise<T>
}

export async function listRegister(filters: URLSearchParams): Promise<RegisterPage> {
  return apiRequest<RegisterPage>(`/api/v1/register?${filters.toString()}`)
}

export async function listOfficers(): Promise<Officer[]> {
  return apiRequest<Officer[]>('/api/v1/register/officers')
}

export async function createRegisterEntry(entry: Record<string, unknown>): Promise<RegisterEntry> {
  return apiRequest<RegisterEntry>('/api/v1/register', { method: 'POST', body: JSON.stringify(entry) })
}

export async function updateRegisterEntry(id: string, changes: Record<string, unknown>): Promise<RegisterEntry> {
  return apiRequest<RegisterEntry>(`/api/v1/register/${id}`, { method: 'PATCH', body: JSON.stringify(changes) })
}

export async function getRegisterAudit(id: string): Promise<AuditItem[]> {
  return apiRequest<AuditItem[]>(`/api/v1/register/${id}/audit`)
}

export async function downloadRegisterCsv(): Promise<Blob> {
  const token = localStorage.getItem('pc-access-token')
  const response = await fetch(`${API}/api/v1/register/export.csv`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!response.ok) throw new Error('Could not export the Register.')
  return response.blob()
}

export async function getDashboard(weekEnding?: string): Promise<DashboardSummary> {
  const params = weekEnding ? `?week_ending=${encodeURIComponent(weekEnding)}` : ''
  return apiRequest<DashboardSummary>(`/api/v1/dashboard${params}`)
}

export async function getDashboardDrill(kpi: string, weekEnding: string, stage?: string): Promise<DrillResult> {
  const params = new URLSearchParams({ week_ending: weekEnding })
  if (stage) params.set('stage', stage)
  return apiRequest<DrillResult>(`/api/v1/dashboard/drill/${kpi}?${params.toString()}`)
}

export async function getTransactions(params: URLSearchParams): Promise<TransactionPage> {
  return apiRequest<TransactionPage>(`/api/v1/transactions?${params.toString()}`)
}

export async function getTransaction(code: string): Promise<TransactionDetail> {
  return apiRequest<TransactionDetail>(`/api/v1/transactions/${encodeURIComponent(code)}`)
}

export async function getTransactionStages(): Promise<Array<{ code: string; label: string }>> {
  return apiRequest<Array<{ code: string; label: string }>>('/api/v1/transactions/stages')
}

export async function createTransaction(values: Record<string, unknown>): Promise<Transaction> {
  return apiRequest<Transaction>('/api/v1/transactions', { method: 'POST', body: JSON.stringify(values) })
}

export async function updateTransaction(code: string, values: Record<string, unknown>): Promise<Transaction> {
  return apiRequest<Transaction>(`/api/v1/transactions/${encodeURIComponent(code)}`, { method: 'PATCH', body: JSON.stringify(values) })
}

export async function addTransactionEvent(code: string, values: Record<string, unknown>): Promise<TransactionEvent> {
  return apiRequest<TransactionEvent>(`/api/v1/transactions/${encodeURIComponent(code)}/events`, { method: 'POST', body: JSON.stringify(values) })
}

export async function getDecisions(): Promise<MinisterDecision[]> {
  return apiRequest<MinisterDecision[]>('/api/v1/decisions')
}

export async function createDecision(values: Record<string, unknown>): Promise<MinisterDecision> {
  return apiRequest<MinisterDecision>('/api/v1/decisions', { method: 'POST', body: JSON.stringify(values) })
}

export async function updateDecision(id: string, values: Record<string, unknown>): Promise<MinisterDecision> {
  return apiRequest<MinisterDecision>(`/api/v1/decisions/${id}`, { method: 'PATCH', body: JSON.stringify(values) })
}

export async function getEngagements(): Promise<Engagement[]> {
  return apiRequest<Engagement[]>('/api/v1/engagements')
}

export async function createEngagement(values: Record<string, unknown>): Promise<Engagement> {
  return apiRequest<Engagement>('/api/v1/engagements', { method: 'POST', body: JSON.stringify(values) })
}

export async function updateEngagement(id: string, values: Record<string, unknown>): Promise<Engagement> {
  return apiRequest<Engagement>(`/api/v1/engagements/${id}`, { method: 'PATCH', body: JSON.stringify(values) })
}

export async function getToolSwitches(): Promise<ToolSwitch[]> { return apiRequest<ToolSwitch[]>('/api/v1/assurance/tools') }
export async function updateToolSwitch(tool: string, suspended: boolean, reason: string): Promise<ToolSwitch> { return apiRequest<ToolSwitch>(`/api/v1/assurance/tools/${encodeURIComponent(tool)}`, { method: 'PATCH', body: JSON.stringify({ suspended, reason }) }) }
export async function getAIRuns(params: URLSearchParams = new URLSearchParams()): Promise<AIRun[]> { return apiRequest<AIRun[]>(`/api/v1/assurance/ai-runs?${params.toString()}`) }
export async function downloadAIRunsCsv(): Promise<Blob> {
  const token=localStorage.getItem('pc-access-token'),response=await fetch(`${API}/api/v1/assurance/ai-runs/export.csv`,{headers:token?{Authorization:`Bearer ${token}`}:{}})
  if(!response.ok)throw new Error('Could not export the AI decision log.')
  return response.blob()
}
export async function approveRegisterProposal(id: string): Promise<RegisterEntry> { return apiRequest<RegisterEntry>(`/api/v1/register/${id}/approve`, { method: 'POST' }) }
export async function rejectRegisterProposal(id: string, reason: string): Promise<RegisterEntry> { return apiRequest<RegisterEntry>(`/api/v1/register/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }) }
export async function getMeetings(): Promise<Meeting[]> { return apiRequest<Meeting[]>('/api/v1/meetings') }
export async function getMeeting(id: string): Promise<Meeting> { return apiRequest<Meeting>(`/api/v1/meetings/${id}`) }
export async function createMeeting(values: Record<string, unknown>): Promise<Meeting> { return apiRequest<Meeting>('/api/v1/meetings', { method: 'POST', body: JSON.stringify(values) }) }
export async function uploadMeetingAudio(id: string, file: File): Promise<Meeting> {
  const token=localStorage.getItem('pc-access-token'),body=new FormData();body.append('file',file)
  const response=await fetch(`${API}/api/v1/meetings/${id}/audio`,{method:'POST',headers:token?{Authorization:`Bearer ${token}`}:{},body})
  if(!response.ok){const error=await response.json().catch(()=>null) as {error?:{message?:string};detail?:string}|null;throw new Error(error?.error?.message??error?.detail??'Could not upload meeting audio.')}
  return response.json() as Promise<Meeting>
}
export async function processMeeting(id:string):Promise<Job>{return apiRequest<Job>(`/api/v1/meetings/${id}/process`,{method:'POST'})}
export async function getJob(id:string):Promise<Job>{return apiRequest<Job>(`/api/v1/jobs/${id}`)}
export async function startMinutesReview(id:string):Promise<Meeting>{return apiRequest<Meeting>(`/api/v1/meetings/${id}/review`,{method:'POST'})}
export async function updateMinutes(id:string,body_markdown:string):Promise<Meeting>{return apiRequest<Meeting>(`/api/v1/meetings/${id}/minutes`,{method:'PATCH',body:JSON.stringify({body_markdown})})}
export async function updateMeetingAction(meetingId:string,actionId:string,values:Record<string,unknown>):Promise<MeetingAction>{return apiRequest<MeetingAction>(`/api/v1/meetings/${meetingId}/actions/${actionId}`,{method:'PATCH',body:JSON.stringify(values)})}
export async function reviewMeetingAction(meetingId:string,actionId:string,decision:'approve'|'reject',reason?:string):Promise<MeetingAction>{return apiRequest<MeetingAction>(`/api/v1/meetings/${meetingId}/actions/${actionId}/review`,{method:'POST',body:JSON.stringify({decision,reason})})}
export async function issueMinutes(id:string):Promise<Meeting>{return apiRequest<Meeting>(`/api/v1/meetings/${id}/issue`,{method:'POST'})}
export async function listDocuments():Promise<{items:SearchDocument[]}>{return apiRequest<{items:SearchDocument[]}>('/api/v1/documents')}
export async function searchRecords(query:string,filters:{doc_type?:string;transaction_id?:string;date_from?:string;date_to?:string}={}):Promise<SearchAnswer>{return apiRequest<SearchAnswer>('/api/v1/records/search',{method:'POST',body:JSON.stringify({query,doc_type:filters.doc_type||null,transaction_id:filters.transaction_id||null,date_from:filters.date_from||null,date_to:filters.date_to||null,top_k:5})})}
export async function uploadDocument(file:File,values:{title:string;doc_type:string;classification:string;source_note:string}):Promise<SearchDocument>{
  const token=localStorage.getItem('pc-access-token'),body=new FormData();body.append('file',file);Object.entries(values).forEach(([key,value])=>body.append(key,String(value)))
  const response=await fetch(`${API}/api/v1/documents`,{method:'POST',headers:token?{Authorization:`Bearer ${token}`}:{},body})
  if(!response.ok){const error=await response.json().catch(()=>null) as {error?:{message?:string};detail?:string}|null;throw new Error(error?.error?.message??error?.detail??'Could not ingest document.')}
  return response.json() as Promise<SearchDocument>
}
export async function openDocumentSource(id:string,page?:number|null):Promise<void>{
  const tab=window.open('about:blank','_blank')
  if(tab)tab.opener=null
  const token=localStorage.getItem('pc-access-token'),response=await fetch(`${API}/api/v1/documents/${id}/source`,{headers:token?{Authorization:`Bearer ${token}`}:{}})
  if(!response.ok)throw new Error('Could not open this source document.')
  const url=URL.createObjectURL(await response.blob()),target=page?`${url}#page=${page}`:url
  if(tab)tab.location.href=target
  else {const link=document.createElement('a');link.href=target;link.target='_blank';link.rel='noopener';link.click()}
  window.setTimeout(()=>URL.revokeObjectURL(url),60000)
}
export async function getDocumentSourceUrl(id:string):Promise<string>{const token=localStorage.getItem('pc-access-token'),response=await fetch(`${API}/api/v1/documents/${id}/source`,{headers:token?{Authorization:`Bearer ${token}`}:{}});if(!response.ok)throw new Error('Could not open this source document.');return URL.createObjectURL(await response.blob())}
export async function getJarvisSession(id:string):Promise<JarvisSession>{return apiRequest<JarvisSession>(`/api/v1/jarvis/sessions/${id}`)}
export async function createJarvisSession():Promise<JarvisSession>{return apiRequest<JarvisSession>('/api/v1/jarvis/sessions',{method:'POST'})}
export async function sendJarvisChat(message:string,sessionId:string|undefined,context:string,onEvent:(name:string,data:Record<string,unknown>)=>void):Promise<void>{
  const token=localStorage.getItem('pc-access-token'),response=await fetch(`${API}/api/v1/jarvis/chat`,{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify({message,session_id:sessionId||null,context:{page:context}})})
  if(!response.ok){const error=await response.json().catch(()=>null) as {error?:{message?:string};detail?:string}|null;throw new Error(error?.error?.message??error?.detail??'Jarvis could not process the request.')}
  if(!response.body)throw new Error('Jarvis stream was unavailable.')
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer=''
  while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true}).replace(/\r\n/g,'\n');let end=buffer.indexOf('\n\n');while(end>=0){const block=buffer.slice(0,end);buffer=buffer.slice(end+2);const event=block.split('\n').find(line=>line.startsWith('event:'))?.slice(6).trim();const data=block.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trim()).join('\n');if(event&&data){try{onEvent(event,JSON.parse(data) as Record<string,unknown>)}catch{}}end=buffer.indexOf('\n\n')}}
}
export async function transcribeJarvis(file:File):Promise<{language:string;text:string}>{
  const token=localStorage.getItem('pc-access-token'),body=new FormData();body.append('file',file)
  const response=await fetch(`${API}/api/v1/jarvis/stt`,{method:'POST',headers:token?{Authorization:`Bearer ${token}`}:{},body})
  if(!response.ok){const error=await response.json().catch(()=>null) as {error?:{message?:string};detail?:string}|null;throw new Error(error?.error?.message??error?.detail??'Voice transcription failed.')}
  return response.json() as Promise<{language:string;text:string}>
}
export async function getComplianceItems():Promise<ComplianceItem[]>{return apiRequest<ComplianceItem[]>('/api/v1/compliance')}
export async function getComplianceDue():Promise<ComplianceItem[]>{return apiRequest<ComplianceItem[]>('/api/v1/compliance/due')}
export async function createComplianceItem(values:Record<string,unknown>):Promise<ComplianceItem>{return apiRequest<ComplianceItem>('/api/v1/compliance',{method:'POST',body:JSON.stringify(values)})}
export async function updateComplianceItem(id:string,values:Record<string,unknown>):Promise<ComplianceItem>{return apiRequest<ComplianceItem>(`/api/v1/compliance/${id}`,{method:'PATCH',body:JSON.stringify(values)})}
export async function getSpotChecks():Promise<SpotCheck[]>{return apiRequest<SpotCheck[]>('/api/v1/assurance/spot-checks')}
export async function createSpotCheck(sample_size=5,period?:string):Promise<SpotCheck>{const params=new URLSearchParams();if(period)params.set('period',period);return apiRequest<SpotCheck>(`/api/v1/assurance/spot-checks${params.size?`?${params}`:''}`,{method:'POST',body:JSON.stringify({sample_size})})}
export async function reconcileSpotCheck(id:string,findings:string):Promise<SpotCheck>{return apiRequest<SpotCheck>(`/api/v1/assurance/spot-checks/${id}`,{method:'PATCH',body:JSON.stringify({findings})})}
export async function getAdminUsers():Promise<AdminUser[]>{return apiRequest<AdminUser[]>('/api/v1/admin/users')}
export async function createAdminUser(values:Record<string,unknown>):Promise<AdminUser>{return apiRequest<AdminUser>('/api/v1/admin/users',{method:'POST',body:JSON.stringify(values)})}
export async function updateAdminUser(id:string,values:Record<string,unknown>):Promise<AdminUser>{return apiRequest<AdminUser>(`/api/v1/admin/users/${id}`,{method:'PATCH',body:JSON.stringify(values)})}
export async function getSystemHealth():Promise<SystemHealth>{return apiRequest<SystemHealth>('/api/v1/admin/health')}
export async function uploadForIntake(file:File,classification:string):Promise<IntakeReview>{const token=localStorage.getItem('pc-access-token'),body=new FormData();body.append('file',file);body.append('classification',classification);const response=await fetch(`${API}/api/v1/intake`,{method:'POST',headers:token?{Authorization:`Bearer ${token}`}:{},body});if(!response.ok){const error=await response.json().catch(()=>null) as {detail?:string}|null;throw new Error(error?.detail??'Could not process this document.')}return response.json() as Promise<IntakeReview>}
export async function getIntakeReviews():Promise<IntakeReview[]>{return apiRequest<IntakeReview[]>('/api/v1/intake')}
export async function getIntakeReview(id:string):Promise<IntakeReview>{return apiRequest<IntakeReview>(`/api/v1/intake/${id}`)}
export async function updateIntakeReview(id:string,payload:IntakePayload):Promise<IntakeReview>{return apiRequest<IntakeReview>(`/api/v1/intake/${id}`,{method:'PATCH',body:JSON.stringify({payload})})}
export async function confirmIntakeReview(id:string):Promise<IntakeReview>{return apiRequest<IntakeReview>(`/api/v1/intake/${id}/confirm`,{method:'POST'})}
export async function handoffIntakeReview(id:string):Promise<IntakeReview>{return apiRequest<IntakeReview>(`/api/v1/intake/${id}/handoff`,{method:'POST'})}
export async function setIntakeCloudPermission(id:string,allowed:boolean):Promise<IntakeReview>{return apiRequest<IntakeReview>(`/api/v1/intake/${id}/cloud-permission`,{method:'PATCH',body:JSON.stringify({allowed})})}
export async function extractPermittedIntake(id:string):Promise<IntakeReview>{return apiRequest<IntakeReview>(`/api/v1/intake/${id}/extract`,{method:'POST'})}
export async function discardIntakeReview(id:string):Promise<void>{const token=localStorage.getItem('pc-access-token'),response=await fetch(`${API}/api/v1/intake/${id}`,{method:'DELETE',headers:token?{Authorization:`Bearer ${token}`}:{}});if(!response.ok){const error=await response.json().catch(()=>null) as {detail?:string}|null;throw new Error(error?.detail??'Could not discard this upload.')}}
export async function listMoittOrganisations():Promise<MoittOrganisation[]>{return apiRequest<MoittOrganisation[]>('/api/v1/organisations')}
export async function listMoittProjects():Promise<MoittProject[]>{return apiRequest<MoittProject[]>('/api/v1/projects')}
