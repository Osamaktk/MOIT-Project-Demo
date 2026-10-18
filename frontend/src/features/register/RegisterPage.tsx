import { useCallback, useMemo, useState } from 'react'
import type { ChangeEvent, FormEvent, KeyboardEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef, type SortingState } from '@tanstack/react-table'
import { ArrowDown, ArrowDownUp, ArrowUp, Download, FileClock, Filter, Plus, Search, ShieldCheck, X } from 'lucide-react'
import { createRegisterEntry, downloadRegisterCsv, getRegisterAudit, listOfficers, listRegister, updateRegisterEntry, type AuditItem, type DemoUser, type Officer, type RegisterEntry } from '../../lib/api'

type FilterValues = { search: string; status: string; priority: string; officerId: string; origin: string; transactionId: string; occurredFrom: string; occurredTo: string; overdue: string }
type SavedFilter = { id: string; name: string; values: FilterValues }

function localDateTime(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

function suggestedDeadline(priority: string): string {
  if (priority === 'C') return ''
  const day = new Date()
  if (priority === 'A') day.setDate(day.getDate() + 1)
  if (priority === 'B') {
    let workdays = 0
    while (workdays < 3) {
      day.setDate(day.getDate() + 1)
      if (day.getDay() !== 0 && day.getDay() !== 6) workdays += 1
    }
  }
  return new Date(day.getTime() - day.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

function displayDate(value: string, language = 'en'): string {
  return new Intl.DateTimeFormat(language === 'ur' ? 'ur-PK' : 'en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(`${value.slice(0, 10)}T00:00:00`))
}

function statusLabel(status: string, translate: (key: string) => string): string {
  return translate(`register.status.${status}`)
}

function csvDownload(blob: Blob) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'decision-action-register.csv'
  anchor.click()
  URL.revokeObjectURL(url)
}

export default function RegisterPage({ user }: { user: DemoUser }) {
  const { t, i18n } = useTranslation()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [officerId, setOfficerId] = useState('')
  const [origin, setOrigin] = useState('')
  const [transactionId, setTransactionId] = useState('')
  const [occurredFrom, setOccurredFrom] = useState('')
  const [occurredTo, setOccurredTo] = useState('')
  const [overdue, setOverdue] = useState('')
  const [offset, setOffset] = useState(0)
  const [pageSize, setPageSize] = useState(50)
  const [tableScrollTop, setTableScrollTop] = useState(0)
  const [sorting, setSorting] = useState<SortingState>([{ id: 'occurred_at', desc: true }])
  const [selected, setSelected] = useState<RegisterEntry | null>(null)
  const [newEntry, setNewEntry] = useState(false)
  const [notice, setNotice] = useState('')
  const storageKey = `pc-register-saved-filters-${user.id}`
  const [savedFilters, setSavedFilters] = useState<SavedFilter[]>(() => {
    try { return JSON.parse(localStorage.getItem(storageKey) ?? '[]') as SavedFilter[] } catch { return [] }
  })
  const [savedFilterId, setSavedFilterId] = useState('')
  const canWrite = user.role === 'cos' || user.role === 'director_td'
  const filters = useMemo(() => {
    const params = new URLSearchParams({ limit: String(pageSize), offset: String(offset) })
    if (search.trim()) params.set('q', search.trim())
    if (status) params.set('status', status)
    if (priority) params.set('priority', priority)
    if (officerId) params.set('officer_id', officerId)
    if (origin) params.set('origin', origin)
    if (transactionId.trim()) params.set('transaction_id', transactionId.trim())
    if (occurredFrom) params.set('occurred_from', occurredFrom)
    if (occurredTo) params.set('occurred_to', occurredTo)
    if (overdue) params.set('overdue', overdue)
    return params
  }, [search, status, priority, officerId, origin, transactionId, occurredFrom, occurredTo, overdue, offset, pageSize])
  const page = useQuery({ queryKey: ['register', filters.toString()], queryFn: () => listRegister(filters) })
  const officers = useQuery({ queryKey: ['register-officers'], queryFn: listOfficers })
  const rowCount = page.data?.items.length ?? 0
  const virtualized = pageSize >= 500
  const virtualRowHeight = 70
  const virtualWindowSize = 40
  const virtualStart = virtualized ? Math.min(Math.max(0, Math.floor(tableScrollTop / virtualRowHeight) - 8), Math.max(0, rowCount - virtualWindowSize)) : 0
  const virtualEnd = virtualized ? Math.min(rowCount, virtualStart + virtualWindowSize) : rowCount
  const handleRowNavigation = useCallback((event: KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const current = Number(event.currentTarget.closest('tr')?.dataset.rowIndex ?? 0)
    const target = event.key === 'Home' ? 0 : event.key === 'End' ? Math.max(0, rowCount - 1) : Math.min(Math.max(0, rowCount - 1), Math.max(0, current + (event.key === 'ArrowDown' ? 1 : -1)))
    const container = event.currentTarget.closest('.register-table-wrap') as HTMLElement | null
    if (virtualized && (target < virtualStart || target >= virtualEnd) && container) {
      container.scrollTop = target * virtualRowHeight
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => container.querySelector<HTMLButtonElement>(`[data-row-index=\"${target}\"] .register-row-open`)?.focus()))
    } else {
      container?.querySelector<HTMLButtonElement>(`[data-row-index=\"${target}\"] .register-row-open`)?.focus()
    }
  }, [rowCount, virtualized, virtualStart, virtualEnd])
  const columns = useMemo<ColumnDef<RegisterEntry>[]>(() => [
    { accessorKey: 'occurred_at', header: '', enableSorting: true },
    { accessorKey: 'serial_no', header: t('register.serial'), cell: info => {
      const entry = info.row.original
      const serial = entry.serial_no == null ? t('register.proposed') : `${entry.fy}/${String(entry.serial_no).padStart(3, '0')}`
      return <button type="button" className="register-row-open" aria-label={`${t('register.openEntry')} ${serial}`} onClick={event => { event.stopPropagation(); setSelected(entry) }} onKeyDown={handleRowNavigation}><span className="register-serial">{entry.serial_no == null ? '?' : serial}</span></button>
    } },
    { accessorKey: 'description', header: t('register.decisionAction'), cell: info => <div className="register-description"><b>{info.getValue<string>()}</b><small>{t(`register.occasion.${info.row.original.occasion_type}`)} · {info.row.original.source_record || t('register.sourceNotEntered')}</small></div> },
    { accessorKey: 'officer.name', id: 'officer', header: t('register.officer'), cell: info => <div className="register-officer"><b>{info.row.original.officer.name}</b><small>{info.row.original.officer.designation}</small></div> },
    { accessorKey: 'deadline', header: t('register.deadline'), cell: info => <span className={info.row.original.overdue ? 'deadline overdue' : 'deadline'}>{displayDate(info.getValue<string>(), i18n.language)}{info.row.original.overdue && <small>{t('register.overdue')}</small>}</span> },
    { accessorKey: 'priority', header: t('register.priority'), cell: info => <span className={`priority-chip priority-${info.getValue<string>().toLowerCase()}`}>{info.getValue<string>()} · {t(`register.priority.${info.getValue<string>().toLowerCase()}`)}</span> },
    { accessorKey: 'status', header: t('register.status'), cell: info => <span className={`status-chip status-${info.getValue<string>()}`}>{statusLabel(info.getValue<string>(), t)}</span> },
  ], [t, i18n.language, handleRowNavigation])
  const table = useReactTable({ data: page.data?.items ?? [], columns, state: { sorting, columnVisibility: { occurred_at: false } }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() })
  const rowModel = table.getRowModel().rows
  const visibleRows = rowModel.slice(virtualStart, virtualEnd)
  const exportMutation = useMutation({ mutationFn: downloadRegisterCsv, onSuccess: csvDownload, onError: error => setNotice(error.message) })
  const clearFilters = () => { setSearch(''); setStatus(''); setPriority(''); setOfficerId(''); setOrigin(''); setTransactionId(''); setOccurredFrom(''); setOccurredTo(''); setOverdue(''); setSavedFilterId(''); setOffset(0) }
  const saveCurrentFilter = () => {
    const name = window.prompt(t('register.filterNamePrompt'))?.trim()
    if (!name) return
    const values = { search, status, priority, officerId, origin, transactionId, occurredFrom, occurredTo, overdue }
    const updated = [...savedFilters, { id: crypto.randomUUID(), name, values }]
    setSavedFilters(updated)
    localStorage.setItem(storageKey, JSON.stringify(updated))
  }
  const applySavedFilter = (id: string) => {
    setSavedFilterId(id)
    const values = savedFilters.find(filter => filter.id === id)?.values
    if (!values) return
    setSearch(values.search); setStatus(values.status); setPriority(values.priority); setOfficerId(values.officerId); setOrigin(values.origin); setTransactionId(values.transactionId); setOccurredFrom(values.occurredFrom); setOccurredTo(values.occurredTo); setOverdue(values.overdue); setOffset(0)
  }
  const removeSavedFilter = () => {
    const updated = savedFilters.filter(filter => filter.id !== savedFilterId)
    setSavedFilters(updated)
    localStorage.setItem(storageKey, JSON.stringify(updated))
    setSavedFilterId('')
  }

  return <div className="register-page">
    <div className="register-heading"><div><div className="eyebrow">{t('register.eyebrow')}</div><h1>{t('register.title')}</h1><p>{t('register.description')}</p></div><div className="register-heading-actions"><button className="outline-button" onClick={() => exportMutation.mutate()} disabled={exportMutation.isPending}><Download size={15}/>{exportMutation.isPending ? t('register.preparing') : t('register.export')}</button>{canWrite && <button className="primary-button" onClick={() => setNewEntry(true)}><Plus size={15}/> {t('register.new')}</button>}</div></div>
    {notice && <div className="register-notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label={t('register.dismiss')}><X size={14}/></button></div>}
    <div className="register-summary"><div><FileClock size={17}/><span><b>{page.data?.total ?? '\u2014'}</b><small>{t('register.matching')}</small></span></div><div><ShieldCheck size={17}/><span><b>{page.data?.items.filter(item => item.overdue).length ?? '\u2014'}</b><small>{t('register.overduePage')}</small></span></div><div className="summary-rule"><span>{t('register.approvedOnly')}</span></div></div>
    <section className="register-panel"><div className="register-toolbar"><div className="register-search"><Search size={15}/><input value={search} onChange={event => { setSearch(event.target.value); setOffset(0) }} placeholder={t('register.search')} aria-label={t('register.search')}/></div><div className="filter-group"><Filter size={14}/><select value={status} onChange={event => { setStatus(event.target.value); setOffset(0) }} aria-label={t('register.filterStatus')}><option value="">{t('register.allStatuses')}</option><option value="open">{t('register.status.open')}</option><option value="in_progress">{t('register.status.in_progress')}</option><option value="closed">{t('register.status.closed')}</option><option value="closed_with_note">{t('register.status.closed_with_note')}</option></select><select value={priority} onChange={event => { setPriority(event.target.value); setOffset(0) }} aria-label={t('register.filterPriority')}><option value="">{t('register.allPriorities')}</option><option value="A">A ? {t('register.priority.a')}</option><option value="B">B ? {t('register.priority.b')}</option><option value="C">C ? {t('register.priority.c')}</option></select><select value={officerId} onChange={event => { setOfficerId(event.target.value); setOffset(0) }} aria-label={t('register.filterOfficer')}><option value="">{t('register.allOfficers')}</option>{(officers.data ?? []).map(officer => <option key={officer.id} value={officer.id}>{officer.name}</option>)}</select><select value={origin} onChange={event => { setOrigin(event.target.value); setOffset(0) }} aria-label={t('register.filterOrigin')}><option value="">{t('register.allOrigins')}</option><option value="manual">{t('register.origin.manual')}</option><option value="ai_proposed">{t('register.origin.ai_proposed')}</option></select><select value={overdue} onChange={event => { setOverdue(event.target.value); setOffset(0) }} aria-label={t('register.filterOverdue')}><option value="">{t('register.allDeadlines')}</option><option value="true">{t('register.overdue')}</option><option value="false">{t('register.notOverdue')}</option></select><button className="clear-filter" onClick={clearFilters}>{t('register.clear')}</button></div><div className="filter-group register-advanced-filters"><label>{t('register.from')}<input type="date" value={occurredFrom} onChange={event => { setOccurredFrom(event.target.value); setOffset(0) }}/></label><label>{t('register.to')}<input type="date" value={occurredTo} onChange={event => { setOccurredTo(event.target.value); setOffset(0) }}/></label><label>{t('register.transactionId')}<input value={transactionId} onChange={event => { setTransactionId(event.target.value); setOffset(0) }} placeholder={t('register.filterTransaction')}/></label></div></div>
      <div className="register-saved-filters"><span>{t('register.savedFilters')}</span><select value={savedFilterId} onChange={event => applySavedFilter(event.target.value)} aria-label={t('register.chooseFilter')}><option value="">{t('register.chooseFilter')}</option>{savedFilters.map(filter => <option key={filter.id} value={filter.id}>{filter.name}</option>)}</select><button onClick={saveCurrentFilter}>{t('register.saveFilters')}</button><button disabled={!savedFilterId} onClick={removeSavedFilter}>{t('register.deleteFilter')}</button></div>
      <div className={`register-table-wrap ${virtualized ? 'virtualized' : ''}`} onScroll={event => { if (virtualized) setTableScrollTop(event.currentTarget.scrollTop) }}><table className="register-table" aria-rowcount={rowModel.length + 1}><thead>{table.getHeaderGroups().map(group => <tr key={group.id}>{group.headers.map(header => <th key={header.id} aria-sort={header.column.getIsSorted() === 'asc' ? 'ascending' : header.column.getIsSorted() === 'desc' ? 'descending' : 'none'}><button className="sort-button" onClick={header.column.getToggleSortingHandler()}>{flexRender(header.column.columnDef.header, header.getContext())}{header.column.getIsSorted() === 'asc' ? <ArrowUp size={12}/> : header.column.getIsSorted() === 'desc' ? <ArrowDown size={12}/> : <ArrowDownUp size={11}/>}</button></th>)}</tr>)}</thead><tbody>{page.isPending ? <tr><td colSpan={columns.length} className="table-state">{t('register.loading')}</td></tr> : page.isError ? <tr><td colSpan={columns.length} className="table-state error">{page.error.message}<button onClick={() => void page.refetch()}>{t('register.retry')}</button></td></tr> : rowModel.length === 0 ? <tr><td colSpan={columns.length} className="table-state"><b>{t('register.noMatches')}</b><span>{t('register.changeFilters')}</span></td></tr> : <>{virtualStart > 0 && <tr aria-hidden="true" className="register-virtual-spacer"><td colSpan={columns.length} style={{ height: virtualStart * virtualRowHeight, padding: 0, border: 0 }}/></tr>}{visibleRows.map((row, index) => <tr key={row.id} data-row-index={virtualStart + index} onClick={() => setSelected(row.original)}>{row.getVisibleCells().map(cell => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}{virtualEnd < rowModel.length && <tr aria-hidden="true" className="register-virtual-spacer"><td colSpan={columns.length} style={{ height: (rowModel.length - virtualEnd) * virtualRowHeight, padding: 0, border: 0 }}/></tr>}</>}</tbody></table></div>
      <div className="register-pagination"><span>{t('register.showing')} {page.data ? Math.min(offset + 1, page.data.total) : 0}{'\u2013'}{Math.min(offset + (page.data?.items.length ?? 0), page.data?.total ?? 0)} {t('register.of')} {page.data?.total ?? '?'} {t('register.approvedRecords')}</span><label className="register-page-size">{t('register.pageSize')}<select value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setOffset(0) }} aria-label={t('register.pageSize')}>{[50, 100, 250, 500, 1000].map(size => <option key={size} value={size}>{size}</option>)}</select></label><div><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>{t('register.previous')}</button><button disabled={!page.data || offset + pageSize >= page.data.total} onClick={() => setOffset(offset + pageSize)}>{t('register.next')}</button></div></div>
    </section>
    <div className="register-footnote"><ShieldCheck size={14}/> {t('register.auditFootnote')}</div>
    {selected && <EntryDrawer entry={selected} canWrite={canWrite} officers={officers.data ?? []} onClose={() => setSelected(null)} onNotice={setNotice}/>}
    {newEntry && <NewEntryDrawer officers={officers.data ?? []} onClose={() => setNewEntry(false)} onCreated={entry => { setNewEntry(false); setOffset(0); setNotice(t('register.notice.created', { serial: `${entry.fy}/${String(entry.serial_no).padStart(3, '0')}` })) }}/>}
  </div>
}

function EntryDrawer({ entry, canWrite, officers, onClose, onNotice }: { entry: RegisterEntry; canWrite: boolean; officers: Officer[]; onClose: () => void; onNotice: (value: string) => void }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [closureNote, setClosureNote] = useState('')
  const audit = useQuery({ queryKey: ['register-audit', entry.id], queryFn: () => getRegisterAudit(entry.id) })
  const mutation = useMutation({ mutationFn: (changes: Record<string, unknown>) => updateRegisterEntry(entry.id, changes), onSuccess: async updated => { await queryClient.invalidateQueries({ queryKey: ['register'] }); await queryClient.invalidateQueries({ queryKey: ['register-audit', entry.id] }); onNotice(t('register.notice.updated', { serial: `${updated.fy}/${String(updated.serial_no).padStart(3, '0')}` })); onClose() }, onError: error => onNotice(error.message) })
  const reassignment = (event: ChangeEvent<HTMLSelectElement>) => {
    const reason = window.prompt(t('register.whyReassign'))
    if (reason?.trim()) mutation.mutate({ officer_id: event.target.value, change_reason: reason.trim() })
  }
  return <div className="drawer-overlay" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}><aside className="record-drawer" aria-label={t('register.drawerTitle')}><div className="drawer-top"><div><span className="eyebrow">{t('register.record')}</span><h2>{entry.serial_no == null ? t('register.proposed') : `${entry.fy}/${String(entry.serial_no).padStart(3, '0')}`}</h2></div><button className="icon-button" onClick={onClose} aria-label={t('register.closeDetails')}><X size={19}/></button></div><div className="drawer-scroll"><div className="drawer-chips"><span className={`status-chip status-${entry.status}`}>{statusLabel(entry.status, t)}</span><span className={`priority-chip priority-${entry.priority.toLowerCase()}`}>{t('register.priorityLabel')} {entry.priority}</span>{entry.overdue && <span className="overdue-chip">{t('register.overdue')}</span>}{entry.origin === 'ai_proposed' && <span className="ai-chip">{t('register.aiDraft')}</span>}</div><h3>{entry.description}</h3><dl className="detail-grid"><dt>{t('register.officer')}</dt><dd>{entry.officer.name}<small>{entry.officer.designation}</small></dd><dt>{t('register.deadline')}</dt><dd className={entry.overdue ? 'overdue-text' : ''}>{displayDate(entry.deadline, i18n.language)}</dd><dt>{t('register.instructionDate')}</dt><dd>{new Intl.DateTimeFormat(i18n.language === 'ur' ? 'ur-PK' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(entry.occurred_at))}</dd><dt>{t('register.occasionType')}</dt><dd>{t(`register.occasion.${entry.occasion_type}`)}{entry.occasion_ref && <small>{entry.occasion_ref}</small>}</dd><dt>{t('register.sourceRecord')}</dt><dd>{entry.source_record || t('register.notRecorded')}</dd><dt>{t('register.ministerWords')}</dt><dd>{entry.minister_words || t('register.noMinisterWords')}</dd><dt>{t('register.originReview')}</dt><dd>{t(`register.origin.${entry.origin}`)} · {entry.review_state}</dd>{entry.closure_note && <><dt>{t('register.closureNote')}</dt><dd>{entry.closure_note}</dd></>}</dl>{entry.ai_assistance && <div className="ai-detail"><span className="ai-chip">{t('register.aiAssisted')}</span><span>Tool: {String(entry.ai_assistance.tool ?? t('register.recordedTool'))}</span><small>{t('register.humanReview')}</small></div>}
      {canWrite && entry.review_state === 'approved' && entry.status !== 'closed' && entry.status !== 'closed_with_note' && <section className="entry-actions"><h4>{t('register.updateStatus')}</h4>{entry.status === 'open' ? <button className="primary-button" disabled={mutation.isPending} onClick={() => mutation.mutate({ status: 'in_progress' })}>{t('register.startProgress')}</button> : <><button className="primary-button" disabled={mutation.isPending} onClick={() => mutation.mutate({ status: 'closed' })}>{t('register.closeAction')}</button><label>{t('register.closeWithNote')}<textarea value={closureNote} onChange={event => setClosureNote(event.target.value)} placeholder={t('register.closePlaceholder')} rows={2}/></label><button className="outline-button" disabled={mutation.isPending || !closureNote.trim()} onClick={() => mutation.mutate({ status: 'closed_with_note', closure_note: closureNote.trim() })}>{t('register.closeWithNote')}</button></>}{!entry.overdue && <label className="reassign-label">{t('register.reassign')}<select defaultValue={entry.officer_id} onChange={reassignment}>{officers.map(officer => <option key={officer.id} value={officer.id}>{officer.name}</option>)}</select></label>}</section>}
      <section className="audit-section"><div className="audit-title"><div><span className="eyebrow">{t('register.traceability')}</span><h4>{t('register.auditHistory')}</h4></div><span>{audit.data?.length ?? '\u2014'} {t('register.events')}</span></div>{audit.isPending ? <p className="audit-empty">{t('register.loadingHistory')}</p> : audit.isError ? <p className="audit-empty error">{audit.error.message}</p> : audit.data?.length ? <ol className="audit-timeline">{audit.data.map(item => <AuditRow key={item.id} item={item}/>)}</ol> : <p className="audit-empty">{t('register.noHistory')}</p>}</section></div><div className="drawer-footer"><span>{t('register.created')} {new Intl.DateTimeFormat(i18n.language === 'ur' ? 'ur-PK' : 'en-GB', { dateStyle: 'medium' }).format(new Date(entry.created_at))}</span><button className="outline-button" onClick={onClose}>{t('register.done')}</button></div></aside></div>
}

function AuditRow({ item }: { item: AuditItem }) {
  const { t, i18n } = useTranslation()
  const summary = t(`register.audit.${item.action}`, { defaultValue: item.action.replaceAll('_', ' ') })
  return <li><span className="timeline-dot"/><div><b>{summary}</b><small>{item.actor_name ?? t('register.system')} · {new Intl.DateTimeFormat(i18n.language === 'ur' ? 'ur-PK' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(item.at))}</small>{item.after?.change_reason != null && <p>{t('register.reason')} {String(item.after.change_reason)}</p>}{item.after?.reason != null && <p>{t('register.reason')} {String(item.after.reason)}</p>}</div></li>
}

function NewEntryDrawer({ officers, onClose, onCreated }: { officers: Officer[]; onClose: () => void; onCreated: (entry: RegisterEntry) => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [occurredAt, setOccurredAt] = useState(localDateTime())
  const [occasionType, setOccasionType] = useState('meeting')
  const [occasionRef, setOccasionRef] = useState('')
  const [description, setDescription] = useState('')
  const [ministerWords, setMinisterWords] = useState('')
  const [officerId, setOfficerId] = useState('')
  const [deadline, setDeadline] = useState(() => suggestedDeadline('B'))
  const [deadlineTouched, setDeadlineTouched] = useState(false)
  const [priority, setPriority] = useState('B')
  const [sourceRecord, setSourceRecord] = useState('')
  const mutation = useMutation({ mutationFn: createRegisterEntry, onSuccess: async entry => { await queryClient.invalidateQueries({ queryKey: ['register'] }); onCreated(entry) } })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    mutation.mutate({ occurred_at: new Date(occurredAt).toISOString(), occasion_type: occasionType, occasion_ref: occasionRef || null, description: description.trim(), minister_words: ministerWords.trim() || null, officer_id: officerId, deadline, priority, source_record: sourceRecord.trim() || null })
  }
  return <div className="drawer-overlay" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}><aside className="record-drawer new-entry-drawer" aria-label={t('register.createTitle')}><div className="drawer-top"><div><span className="eyebrow">{t('register.manual')}</span><h2>{t('register.recordDecision')}</h2></div><button className="icon-button" onClick={onClose} aria-label={t('register.closeDetails')}><X size={19}/></button></div><form className="new-entry-form" onSubmit={submit}><p>{t('register.manualNotice')}</p><label>{t('register.decisionInstruction')}<textarea required minLength={3} maxLength={4000} value={description} onChange={event => setDescription(event.target.value)} rows={4} placeholder={t('register.decisionPlaceholder')}/></label><label>{t('register.meetingTime')}<input required type="datetime-local" value={occurredAt} onChange={event => setOccurredAt(event.target.value)}/></label><div className="form-row"><label>{t('register.occasionType')}<select value={occasionType} onChange={event => setOccasionType(event.target.value)}><option value="meeting">{t('register.occasion.meeting')}</option><option value="engagement">{t('register.occasion.engagement')}</option><option value="file">{t('register.occasion.file')}</option><option value="on_the_move">{t('register.occasion.on_the_move')}</option></select></label><label>{t('register.priorityLabel')}<select value={priority} onChange={event => { setPriority(event.target.value); if (!deadlineTouched) setDeadline(suggestedDeadline(event.target.value)) }}><option value="A">A ? {t('register.priority.a')}</option><option value="B">B ? {t('register.priority.b')}</option><option value="C">C ? {t('register.priority.c')}</option></select></label></div><label>{t('register.occasionReference')}<input value={occasionRef} onChange={event => setOccasionRef(event.target.value)} maxLength={255} placeholder={t('register.meetingFileRef')}/></label><label>{t('register.officer')}<select required value={officerId} onChange={event => setOfficerId(event.target.value)}><option value="">{t('register.selectOfficer')}</option>{officers.map(officer => <option key={officer.id} value={officer.id}>{officer.name} · {officer.designation}</option>)}</select></label><label>{t('register.deadline')}<input required type="date" value={deadline} onChange={event => { setDeadline(event.target.value); setDeadlineTouched(true) }}/><small>{t('register.calendarDeadline')}</small></label><label>{t('register.sourceRecord')}<input value={sourceRecord} onChange={event => setSourceRecord(event.target.value)} maxLength={255} placeholder={t('register.sourcePlaceholder')}/></label><label>Minister’s words <span className="optional-label">{t('register.optional')}</span><textarea value={ministerWords} onChange={event => setMinisterWords(event.target.value)} maxLength={2000} rows={2} placeholder={t('register.wordsPlaceholder')}/></label>{mutation.isError && <div className="error-box" role="alert">{mutation.error.message}</div>}<div className="new-entry-footer"><button type="button" className="outline-button" onClick={onClose}>{t('register.cancel')}</button><button className="primary-button" disabled={mutation.isPending || !officerId}>{mutation.isPending ? t('register.saving') : t('register.saveOfficial')}</button></div></form></aside></div>
}
