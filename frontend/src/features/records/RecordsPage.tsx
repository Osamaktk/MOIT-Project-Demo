import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, FileSearch, FileText, FolderOpen, Search, ShieldCheck, Upload } from 'lucide-react'
import { getTransactions, listDocuments, openDocumentSource, searchRecords, uploadDocument, type SearchCitation } from '../../lib/api'
import './records.css'

const types = ['board_paper', 'cabinet_paper', 'ccop', 'wing_paper', 'minute', 'brief', 'register', 'other']

export default function RecordsPage() {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('')
  const [transactionId, setTransactionId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [answer, setAnswer] = useState<Awaited<ReturnType<typeof searchRecords>> | null>(null)
  const [selected, setSelected] = useState<SearchCitation | null>(null)
  const [error, setError] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [docType, setDocType] = useState('other')
  const [classification, setClassification] = useState('internal')
  const [sourceNote, setSourceNote] = useState('')
  const role = localStorage.getItem('pc-role')
  const canIngest = role === 'cos' || role === 'data_coordinator'
  const canClassifyConfidential = role === 'cos'
  const client = useQueryClient()
  const documents = useQuery({ queryKey: ['documents'], queryFn: listDocuments })
  const transactions = useQuery({ queryKey: ['transactions', 'records-search'], queryFn: () => getTransactions(new URLSearchParams({ limit: '100' })) })
  const search = useMutation({
    mutationFn: () => searchRecords(query, { doc_type: filter, transaction_id: transactionId, date_from: dateFrom, date_to: dateTo }),
    onSuccess: value => { setAnswer(value); setSelected(value.citations[0] ?? null); setError('') },
    onError: reason => setError(reason instanceof Error ? reason.message : t('records.searchError')),
  })
  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error(t('records.chooseDocumentFirst'))
      return uploadDocument(file, { title: title.trim() || file.name, doc_type: docType, classification, source_note: sourceNote.trim() })
    },
    onSuccess: () => { client.invalidateQueries({ queryKey: ['documents'] }); setFile(null); setTitle(''); setSourceNote(''); setError('') },
    onError: reason => setError(reason instanceof Error ? reason.message : t('records.ingestError')),
  })
  function submit(event: FormEvent) { event.preventDefault(); if (query.trim()) search.mutate() }
  function submitUpload(event: FormEvent) { event.preventDefault(); upload.mutate() }
  async function openSource(citation: SearchCitation) {
    try { await openDocumentSource(citation.document_id, citation.page) }
    catch (reason) { setError(reason instanceof Error ? reason.message : t('records.openSourceError')) }
  }
  const docTypeLabel = (type: string) => t(`records.docType.${type}`, { defaultValue: type.replaceAll('_', ' ') })

  return <div className="records-page">
    <div className="page-heading records-heading">
      <div><div className="eyebrow">{t('records.eyebrow')}</div><h1>{t('records.title')}</h1><p>{t('records.summary')}</p></div>
      <div className="records-clearance"><ShieldCheck size={16}/> {t('records.clearance')}: {t(canClassifyConfidential ? 'records.clearanceAll' : 'records.clearanceStandard')}</div>
    </div>
    <form className="records-searchbar" onSubmit={submit}>
      <Search size={20}/>
      <input value={query} onChange={event => setQuery(event.target.value)} placeholder={t('records.searchPlaceholder')} aria-label={t('records.searchLabel')}/>
      <select value={filter} onChange={event => setFilter(event.target.value)} aria-label={t('records.filterType')}><option value="">{t('records.allTypes')}</option>{types.map(type => <option key={type} value={type}>{docTypeLabel(type)}</option>)}</select>
      <select value={transactionId} onChange={event => setTransactionId(event.target.value)} aria-label={t('records.filterTransaction')}><option value="">{t('records.allTransactions')}</option>{transactions.data?.items.map(tx => <option key={tx.id} value={tx.id}>{tx.code} · {tx.name}</option>)}</select>
      <label className="records-date-filter">{t('records.from')}<input type="date" value={dateFrom} onChange={event => setDateFrom(event.target.value)} aria-label={t('records.createdFrom')}/></label>
      <label className="records-date-filter">{t('records.to')}<input type="date" value={dateTo} onChange={event => setDateTo(event.target.value)} aria-label={t('records.createdTo')}/></label>
      <button className="primary-button" disabled={search.isPending || query.trim().length < 2}>{search.isPending ? t('records.searching') : t('records.search')}<span><Search size={15}/></span></button>
    </form>
    {error && <div className="error-box" role="alert">{error}</div>}
    <div className="records-layout">
      <section className="records-answer card">
        <div className="records-section-head"><div><div className="eyebrow">{t('records.groundedResponse')}</div><h2>{answer ? (answer.declined ? t('records.noEvidence') : t('records.results')) : t('records.askRecords')}</h2></div><span className="records-zone">{t('records.indexedRecords')}</span></div>
        {answer ? <><p className={answer.declined ? 'records-declined' : 'records-answer-text'}>{answer.answer}</p>{answer.citations.length > 0 && <div className="records-citation-list"><h3>{t('records.sources')}</h3>{answer.citations.map(citation => <button key={citation.number} className={`records-citation ${selected?.number === citation.number ? 'selected' : ''}`} onClick={() => setSelected(citation)}><span className="citation-number">[{citation.number}]</span><span><b>{citation.title}</b><small>{citation.section || docTypeLabel(citation.doc_type)}{citation.page ? ` · ${t('records.page')} ${citation.page}` : ''}</small></span><ExternalLink size={15}/></button>)}</div>}</> : <div className="records-empty"><FileSearch size={28}/><b>{t('records.searchAcross')}</b><span>{t('records.excerptHelp')}</span></div>}
      </section>
      <aside className="records-source card"><div className="eyebrow">{t('records.sourceViewer')}</div>{selected ? <><h2>{selected.title}</h2><div className="source-meta">{docTypeLabel(selected.doc_type)}{selected.page ? ` · ${t('records.page')} ${selected.page}` : ''}{selected.section ? ` · ${selected.section}` : ''}</div><blockquote>{selected.snippet}</blockquote><button className="secondary-button" onClick={() => void openSource(selected)}>{t('records.openOriginal')} <ExternalLink size={15}/></button></> : <div className="source-placeholder"><FolderOpen size={24}/><span>{t('records.chooseCitation')}</span></div>}</aside>
    </div>
    <section className="records-library card"><div className="records-section-head"><div><div className="eyebrow">{t('records.library')}</div><h2>{t('records.indexedRecordsTitle')} <span className="records-count">{documents.data?.items.length ?? 0}</span></h2></div><span className="muted">PDF · DOCX · TXT · MD</span></div>{documents.isLoading ? <p className="muted">{t('records.loadingLibrary')}</p> : (documents.data?.items.length ?? 0) === 0 ? <p className="muted">{t('records.noDocuments')}</p> : <div className="records-doc-list">{documents.data?.items.map(document => <div className="records-doc-row" key={document.id}><FileText size={18}/><div><b>{document.title}</b><small>{docTypeLabel(document.doc_type)} · {t(`records.classification.${document.classification}`, { defaultValue: document.classification })} · {t('records.chunkCount', { count: document.chunk_count })}</small></div><span className="doc-ingest-status">{t(`records.ingestStatus.${document.ingest_status}`, { defaultValue: document.ingest_status })}</span></div>)}</div>}</section>
    {canIngest && <section className="records-ingest card"><div className="records-section-head"><div><div className="eyebrow">{t('records.dataCoordination')}</div><h2>{t('records.ingestDocument')}</h2></div><span className="muted">{t('records.maximumSize')}</span></div><form onSubmit={submitUpload} className="records-upload-form"><label className="records-file-field"><Upload size={17}/><span>{file?.name ?? t('records.chooseFile')}</span><input type="file" accept=".pdf,.docx,.txt,.md" onChange={event => setFile(event.target.files?.[0] ?? null)} required/></label><label>{t('records.documentTitle')}<input value={title} onChange={event => setTitle(event.target.value)} placeholder={t('records.filenameFallback')}/></label><label>{t('records.documentType')}<select value={docType} onChange={event => setDocType(event.target.value)}>{types.map(type => <option key={type} value={type}>{docTypeLabel(type)}</option>)}</select></label><label>{t('records.classificationLabel')}<select value={classification} onChange={event => setClassification(event.target.value)}><option value="public">{t('records.classification.public')}</option><option value="internal">{t('records.classification.internal')}</option>{canClassifyConfidential && <option value="confidential">{t('records.classification.confidential')}</option>}</select></label><label>{t('records.sourceNote')}<input value={sourceNote} onChange={event => setSourceNote(event.target.value)} placeholder={t('records.optionalReference')}/></label><button className="primary-button" disabled={upload.isPending || !file}>{upload.isPending ? t('records.ingesting') : t('records.ingest')}<span><Upload size={15}/></span></button></form></section>}
  </div>
}
