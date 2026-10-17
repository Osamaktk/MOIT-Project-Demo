import { lazy, Suspense, useEffect, useRef, useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Activity, Building2, ChevronDown, Command, FileClock, FileSearch, Gavel, LayoutDashboard, LogOut, Menu, ShieldCheck, UsersRound } from 'lucide-react'
import { getHealth, getMe, getToolSwitches, login, type DemoUser } from '../lib/api'
import RegisterPage from '../features/register/RegisterPage'
import '../features/transactions/workflows.css'
import '../features/assurance/assurance.css'
import '../features/meetings/meetings.css'
import '../styles/command-palette.css'
import JarvisDock from '../features/jarvis/JarvisDock'

const DashboardPage = lazy(() => import('../features/dashboard/DashboardPage'))
const TransactionsPage = lazy(() => import('../features/transactions/TransactionsPage'))
const DecisionsPage = lazy(() => import('../features/decisions/DecisionsPage'))
const EngagementsPage = lazy(() => import('../features/engagements/EngagementsPage'))
const AssurancePage = lazy(() => import('../features/assurance/AssurancePage'))
const ReviewQueuePage = lazy(() => import('../features/assurance/ReviewQueuePage'))
const MeetingsPage = lazy(() => import('../features/meetings/MeetingsPage'))
const RecordsPage = lazy(() => import('../features/records/RecordsPage'))
const CompliancePage = lazy(() => import('../features/compliance/CompliancePage'))
const AdminPage = lazy(() => import('../features/admin/AdminPage'))

const navItems = [
  { label: 'nav.commandCenter', icon: LayoutDashboard, path: '/' },
  { label: 'nav.register', icon: FileClock, path: '/register' },
  { label: 'nav.reviewQueue', icon: ShieldCheck, path: '/review', reviewer: true },
  { label: 'nav.meetings', icon: UsersRound, path: '/meetings' },
  { label: 'nav.transactions', icon: Building2, path: '/transactions' },
  { label: 'nav.recordsSearch', icon: FileSearch, path: '/search' },
  { label: 'nav.compliance', icon: Gavel, path: '/compliance' },
  { label: 'nav.engagements', icon: Activity, path: '/engagements' },
  { label: 'nav.assurance', icon: ShieldCheck, path: '/assurance' },
  { label: 'nav.admin', icon: UsersRound, path: '/admin', admin: true },
]

function LoginPage({ onLogin }: { onLogin: (user: DemoUser, token: string) => void }) {
  const { t, i18n } = useTranslation()
  const [email, setEmail] = useState('minister@demo.example')
  const [password, setPassword] = useState('Demo-Only-Change-Me-2026!')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    document.documentElement.lang = i18n.language === 'ur' ? 'ur' : 'en'
    document.documentElement.dir = i18n.language === 'ur' ? 'rtl' : 'ltr'
    localStorage.setItem('pc-language', i18n.language === 'ur' ? 'ur' : 'en')
  }, [i18n.language])
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try { const result = await login(email, password); const user = await getMe(result.access_token); onLogin(user, result.access_token) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not sign in.') }
    finally { setBusy(false) }
  }
  return <main className="login-screen"><button className="locale-toggle" onClick={()=>void i18n.changeLanguage(i18n.language==='ur'?'en':'ur')}>{t('shell.nextLanguage')}</button><div className="login-brand"><div className="brand-mark"><Command size={24}/></div><div><strong>PC Command Center</strong><span>{t('login.tagline')}</span></div></div><form className="login-card" onSubmit={submit}><div className="eyebrow">{t('login.secure')}</div><h1>{t('login.welcome')}</h1><p className="muted">{t('login.description')}</p><label>{t('login.email')}<input type="email" required value={email} onChange={e=>setEmail(e.target.value)} autoComplete="username"/></label><label>{t('login.password')}<input type="password" required value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password"/></label>{error && <div className="error-box" role="alert">{error}</div>}<button className="primary-button full" disabled={busy}>{busy ? t('login.signingIn') : t('login.signIn')} <span>{'\u2192'}</span></button><div className="synthetic-note"><ShieldCheck size={15}/> {t('login.synthetic')}</div></form><div className="login-footer">{t('login.office')}</div></main>
}

function AppShell({ user, onLogout }: { user: DemoUser; onLogout: () => void }) {
  const { t, i18n } = useTranslation()
  const [zone, setZone] = useState('unavailable')
  const location = useLocation()
  const switches = useQuery({ queryKey: ['tool-switches'], queryFn: getToolSwitches, refetchInterval: 5000 })
  const suspendedTools = switches.data?.filter(row => row.suspended).map(row => row.tool) ?? []
  const toolStatusKey = switches.isPending || switches.isError ? 'shell.toolsUnknown' : suspendedTools.length ? 'shell.toolsSuspended' : 'shell.toolsOnline'
  useEffect(() => { let active = true; getHealth().then(data => { if (active) setZone(data.ai_zone) }).catch(() => { if (active) setZone('unavailable') }); return () => { active = false } }, [])
  const [menu, setMenu] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const visible = navItems.filter(item => (!item.admin || user.role === 'admin') && (!item.reviewer || ['cos', 'director_td'].includes(user.role)))
  useEffect(() => {
    document.documentElement.lang = i18n.language === 'ur' ? 'ur' : 'en'
    document.documentElement.dir = i18n.language === 'ur' ? 'rtl' : 'ltr'
    localStorage.setItem('pc-language', i18n.language === 'ur' ? 'ur' : 'en')
  }, [i18n.language])
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setPaletteOpen(true) }
      if (event.key === 'Escape') setPaletteOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])
  return <div className="app-shell"><aside className={`sidebar ${drawer ? 'open' : ''}`}><div className="sidebar-brand"><div className="brand-mark small"><Command size={19}/></div><div><strong>PC Command</strong><span>OFFICE SYSTEM</span></div></div><div className="rail-label">{t('shell.workspace').toUpperCase()}</div><nav>{visible.map(({label,icon:Icon,path})=><NavLink key={path} end={path==='/'} to={path} onClick={()=>setDrawer(false)} className={({isActive})=>`nav-item ${isActive?'active':''}`}><Icon size={17}/><span>{t(label)}</span></NavLink>)}</nav><div className="sidebar-bottom"><div className="side-status"><span className="status-dot"/> {t('shell.coreReady')}</div><div className="version">{t('shell.demoEnvironment')}</div></div></aside>{drawer&&<button className="scrim" aria-label={t('shell.closeNavigation')} onClick={()=>setDrawer(false)}/>}<div className="main-column"><header className="topbar"><button className="icon-button mobile-menu" onClick={()=>setDrawer(!drawer)} aria-label={t('shell.toggleNavigation')}><Menu size={20}/></button><div className="breadcrumb">{t('shell.workspace')} <span>/</span> <b>{t('shell.commandCenter')}</b></div><div className="top-actions"><button className="search-command" aria-label={t('shell.search')} onClick={()=>setPaletteOpen(true)}><Command size={14}/> <span>{t('shell.search')}</span><kbd>Ctrl K</kbd></button><button className="language-button" aria-label={t('shell.changeLanguage')} onClick={()=>void i18n.changeLanguage(i18n.language==='ur'?'en':'ur')}>{t('shell.nextLanguage')}</button><div className={`tool-status-pill ${suspendedTools.length ? 'suspended' : ''}`} role="status" aria-label={t('shell.toolStatusLabel')}><span/>{t(toolStatusKey)}</div><div className="zone-pill"><span/> {t('shell.zone')}: {t(`shell.zone.${zone}`,{defaultValue:zone})} <small>{t(`shell.zoneMode.${zone}`,{defaultValue:''})}</small></div><div className="user-wrap"><button className="user-button" onClick={()=>setMenu(!menu)}><span className="avatar">{user.name.split(' ').map(n=>n[0]).join('')}</span><span className="user-meta"><b>{user.name}</b><small>{user.designation}</small></span><ChevronDown size={14}/></button>{menu&&<div className="user-menu"><div className="user-menu-role">{t('shell.signedInAs')} <b>{t(`admin.role.${user.role}`,{defaultValue:user.role.replaceAll('_',' ')})}</b></div><button onClick={onLogout}><LogOut size={15}/> {t('shell.signOut')}</button></div>}</div></div></header><main className="content">{((location.pathname.startsWith("/meetings") && suspendedTools.includes("minutes_assistant")) || (location.pathname.startsWith("/search") && suspendedTools.includes("records_search")) || (location.pathname === "/" && suspendedTools.includes("brief_generator"))) && <div className="ai-suspended-banner" role="alert"><ShieldCheck size={15}/> {t('shell.toolSuspendedBanner')}</div>}<Suspense fallback={<div className="loading-screen">{t('shell.loadingWorkspace')}</div>}><Routes><Route path="/" element={<DashboardPage/>} /><Route path="/register" element={<RegisterPage user={user}/>} /><Route path="/meetings" element={<MeetingsPage/>} /><Route path="/search" element={<RecordsPage/>} /><Route path="/transactions" element={<TransactionsPage/>} /><Route path="/transactions/:code" element={<TransactionsPage/>} /><Route path="/decisions" element={<DecisionsPage/>} /><Route path="/engagements" element={<EngagementsPage/>} /><Route path="/compliance" element={<CompliancePage/>} /><Route path="/admin" element={<AdminPage/>} /><Route path="/assurance" element={<AssurancePage/>} /><Route path="/review" element={<ReviewQueuePage/>} /><Route path="*" element={<ModuleLanding/>}/></Routes></Suspense></main></div><JarvisDock user={user} suspended={suspendedTools.includes("jarvis")} context={location.pathname}/>{paletteOpen&&<CommandPalette items={visible} onClose={()=>setPaletteOpen(false)}/>}</div>
}

function CommandPalette({items,onClose}:{items:typeof navItems;onClose:()=>void}) {
  const [query,setQuery]=useState('')
  const input=useRef<HTMLInputElement>(null)
  const navigate=useNavigate()
  useEffect(()=>{input.current?.focus()},[])
  const {t}=useTranslation()
  const commands=[...items,{label:'nav.decisions',icon:Gavel,path:'/decisions'}].filter((item,index,all)=>all.findIndex(candidate=>candidate.path===item.path)===index)
  const matches=commands.filter(item=>t(item.label).toLowerCase().includes(query.trim().toLowerCase()))
  return <div className="command-overlay" onMouseDown={event=>{if(event.target===event.currentTarget)onClose()}}><section className="command-dialog" role="dialog" aria-modal="true" aria-label={t('shell.commandPalette')}><div className="command-input-row"><Command size={17}/><input ref={input} value={query} onChange={event=>setQuery(event.target.value)} placeholder={t('shell.findPage')} aria-label={t('shell.filterPages')}/><button className="icon-button" onClick={onClose} aria-label={t('shell.closeCommandPalette')}>Esc</button></div><div className="command-results">{matches.map(item=><button key={item.path} onClick={()=>{onClose();navigate(item.path)}}><item.icon size={16}/><span>{t(item.label)}</span><kbd>{item.path}</kbd></button>)}{matches.length===0&&<p role="status">{t('shell.noPagesMatch')}</p>}</div><footer>{t('shell.paletteHelp')}</footer></section></div>
}

function ModuleLanding() { const {t}=useTranslation(); return <div className="module-placeholder"><div className="placeholder-mark"><FileClock size={22}/></div><div className="eyebrow">{t('shell.workspace').toUpperCase()}</div><h1>{t('shell.pageNotFound')}</h1><p>{t('shell.pageMissing')}</p><NavLink to="/" className="primary-button">{t('shell.returnCommandCenter')} <span>{'\u2192'}</span></NavLink></div> }

export default function App() {
  const { t } = useTranslation()
  const [user, setUser] = useState<DemoUser | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('pc-access-token'))
  const [checking, setChecking] = useState(Boolean(token))
  const navigate = useNavigate()
  useEffect(()=>{ if(token) getMe(token).then(nextUser=>{localStorage.setItem('pc-role',nextUser.role);localStorage.setItem('pc-user-id',nextUser.id);setUser(nextUser)}).catch(()=>{localStorage.removeItem('pc-role');localStorage.removeItem('pc-user-id');localStorage.removeItem('pc-access-token');setToken(null)}).finally(()=>setChecking(false)) },[token])
  function onLogin(nextUser: DemoUser, nextToken: string) { localStorage.setItem('pc-role',nextUser.role);localStorage.setItem('pc-user-id',nextUser.id);localStorage.setItem('pc-access-token',nextToken);setToken(nextToken);setUser(nextUser);navigate('/') }
  function onLogout() { localStorage.removeItem('pc-role');localStorage.removeItem('pc-user-id');localStorage.removeItem('pc-access-token');setToken(null);setUser(null) }
  if(checking)return <div className="loading-screen">{t('shell.loadingSecureWorkspace')}</div>
  if(!user)return <LoginPage onLogin={onLogin}/>
  return <AppShell user={user} onLogout={onLogout}/>
}
