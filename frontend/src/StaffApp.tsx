import { useEffect, useState, type FormEvent } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { ArrowRight, Bell, ChefHat, Check, ClipboardList, CreditCard, LogOut, Menu as MenuIcon, RefreshCw, Settings2, ShoppingBag, Store, UtensilsCrossed, X } from 'lucide-react'
import { api, ApiError } from './api'
import type { Config, Order } from './types'
import MenuStudio, { type CatalogueRow } from './MenuStudio'
import DiningTables, { type DiningTable } from './DiningTables'
import StaffModal from './StaffModal'
import './staff.css'

type Section = 'overview' | 'kitchen' | 'tables' | 'menu' | 'settings'
type StaffUser = { id: string; email: string; full_name: string }
type Outlet = { id: string; brand_id: string; tenant_id: string; name: string; brand_name: string; ordering_enabled: boolean; can_edit_brand: boolean; roles: string[] }
type Table = DiningTable
type QueueLine = { line_id: string; order_id: string; visit_id: string; display_ref: string; table_label: string; item_name: string; variant_name: string; notes: string; quantity: number; queued_qty: number; preparing_qty: number; ready_qty: number; revision: number; modifiers: { group_name: string; option_name: string }[] }
type ServiceRequest = { id: string; visit_id: string; table_label: string; kind: 'WAITER' | 'BILL'; requested_at: string }
type Reconciliation = { id: string; status: 'OPEN' | 'CHECKOUT' | 'CLOSED'; submitted_subtotal_paise: number; effective_subtotal_paise: number; order_count: number; outstanding_units: number; open_service_requests: number }
type VisitDetail = { visit_id: string; orders: Order[]; reconciliation: Reconciliation }

const money = (paise: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(paise / 100)

function StaffLogin({ onLogin }: { onLogin: (user: StaffUser) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try { onLogin(await api.post<StaffUser>('/api/v1/staff/login', { email, password })) }
    catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="staff-login-page"><div className="staff-login-aside"><div className="staff-login-brand"><UtensilsCrossed size={24} /> DineBridge</div><div><span className="staff-kicker">THE RESTAURANT WORKSPACE</span><h1>Every table.<br />In good hands.</h1><p>Orders, service, kitchen and billing in one calm place.</p></div><div className="staff-login-footer">Made for the moments behind a great meal.</div></div><div className="staff-login-form-wrap"><form className="staff-login-form" onSubmit={submit}><div className="staff-mobile-brand"><UtensilsCrossed size={20} /> DineBridge</div><span className="staff-kicker">WELCOME BACK</span><h2>Sign in to your portal</h2><p>Use the staff account created for your restaurant.</p><label>Email address<input type="email" autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} required placeholder="you@restaurant.com" /></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required placeholder="Enter your password" /></label>{error && <div className="staff-alert error" role="alert">{error}</div>}<button className="staff-primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <ArrowRight size={17} /></button><small>Need access? Ask your restaurant owner to add a staff account.</small></form></div></div>
}

export default function StaffApp() {
  const [user, setUser] = useState<StaffUser | null>(null)
  const [checking, setChecking] = useState(true)
  const [outlets, setOutlets] = useState<Outlet[]>([])
  const [outletId, setOutletId] = useState('')
  const [section, setSection] = useState<Section>('overview')
  const [tables, setTables] = useState<Table[]>([])
  const [queue, setQueue] = useState<QueueLine[]>([])
  const [requests, setRequests] = useState<ServiceRequest[]>([])
  const [catalogue, setCatalogue] = useState<CatalogueRow[]>([])
  const [config, setConfig] = useState<Config | null>(null)
  const [detail, setDetail] = useState<VisitDetail | null>(null)
  const [selectedTable, setSelectedTable] = useState<Table | null>(null)
  const [qr, setQr] = useState<{ url: string; label: string } | null>(null)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [pendingOrdering, setPendingOrdering] = useState(false)
  const [switchOutletOpen, setSwitchOutletOpen] = useState(false)
  const [brandName, setBrandName] = useState('')
  const [primaryColor, setPrimaryColor] = useState('#263b32')
  const [accentColor, setAccentColor] = useState('#d97a55')
  const [billRef, setBillRef] = useState('')
  const [billAmount, setBillAmount] = useState('')
  const [billMethod, setBillMethod] = useState('')

  const outlet = outlets.find(entry => entry.id === outletId)
  const canManage = !!outlet?.roles.some(role => role === 'OWNER' || role === 'MANAGER')
  const canBill = !!outlet?.roles.some(role => role === 'OWNER' || role === 'MANAGER' || role === 'CASHIER')
  const activeTables = tables.filter(table => table.visit_id)
  const unseenCount = tables.reduce((sum, table) => sum + Number(table.unseen_orders || 0), 0)

  useEffect(() => { void bootstrap() }, [])
  useEffect(() => { document.title = 'DineBridge · Staff Portal' }, [])
  useEffect(() => { setPendingOrdering(!!config?.ordering_enabled) }, [config?.ordering_enabled, outletId])
  useEffect(() => { if (!notice && !error) return; const timer = window.setTimeout(() => { setNotice(''); setError('') }, 4500); return () => window.clearTimeout(timer) }, [notice, error])
  useEffect(() => {
    if (!outletId || !user) return
    void refresh(outletId)
    const timer = window.setInterval(() => void refresh(outletId, true), 10000)
    return () => window.clearInterval(timer)
  }, [outletId, user?.id])

  async function bootstrap() {
    setChecking(true)
    try {
      const [person, available] = await Promise.all([api.get<StaffUser>('/api/v1/staff/me'), api.get<{ outlets: Outlet[] }>('/api/v1/staff/outlets')])
      setUser(person); setOutlets(available.outlets)
      setOutletId(current => available.outlets.some(entry => entry.id === current) ? current : available.outlets[0]?.id || '')
    } catch (failure) {
      if ((failure as ApiError).status !== 401) setError((failure as Error).message)
      setUser(null)
    } finally { setChecking(false) }
  }
  async function refresh(id: string, quiet = false) {
    try {
      const [tableData, queueData, requestData, outletConfig] = await Promise.all([
        api.get<{ tables: Table[] }>(`/api/v1/staff/outlets/${id}/tables`),
        api.get<{ lines: QueueLine[] }>(`/api/v1/staff/outlets/${id}/queue`),
        api.get<{ requests: ServiceRequest[] }>(`/api/v1/staff/outlets/${id}/service-requests`),
        api.config(id),
      ])
      setTables(tableData.tables); setQueue(queueData.lines); setRequests(requestData.requests); setConfig(outletConfig)
      if (!quiet) { setBrandName(outletConfig.display_name); setPrimaryColor(outletConfig.primary_color); setAccentColor(outletConfig.accent_color) }
      setLastUpdated(new Date()); setError('')
      const selected = outlets.find(entry => entry.id === id)
      if (selected?.roles.some(role => role === 'OWNER' || role === 'MANAGER')) {
        const data = await api.get<{ items: CatalogueRow[] }>(`/api/v1/staff/outlets/${id}/catalogue`)
        setCatalogue(data.items)
      }

    } catch (failure) { setError((failure as Error).message) }
  }
  async function action(work: () => Promise<unknown>, success: string, after?: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('')
    try { await work(); setNotice(success); await refresh(outletId, true); if (after) await after(); return true }
    catch (failure) { setError((failure as Error).message); return false }
    finally { setBusy(false) }
  }
  async function openTable(table: Table) {
    setSelectedTable(table); setDetail(null); setBillRef(''); setBillAmount(''); setBillMethod('')
    if (table.visit_id) {
      try { setDetail(await api.get<VisitDetail>(`/api/v1/staff/visits/${table.visit_id}/orders`)) }
      catch (failure) { setError((failure as Error).message) }
    }
  }
  async function reloadDetail() {
    if (selectedTable?.visit_id) setDetail(await api.get<VisitDetail>(`/api/v1/staff/visits/${selectedTable.visit_id}/orders`))
  }
  async function progress(line: QueueLine, to_state: 'PREPARING' | 'READY' | 'SERVED', quantity: number) {
    await action(() => api.patch(`/api/v1/staff/lines/${line.line_id}/progress`, { to_state, quantity, expected_revision: line.revision }), `${quantity} ${quantity === 1 ? 'item' : 'items'} moved to ${to_state.toLowerCase()}.`)
  }
  async function createTable(label: string, seating_capacity: number) {
    const result = await api.post<{ qr_url: string; label: string }>(`/api/v1/staff/outlets/${outletId}/tables`, { label, seating_capacity })
    setQr({ url: result.qr_url, label: result.label }); await refresh(outletId, true); setNotice('Table created. Save or print its QR code.')
  }
  async function deleteTable(table: Table) {
    try {
      await api.delete(`/api/v1/staff/tables/${table.id}`)
      if (selectedTable?.id === table.id) { setSelectedTable(null); setDetail(null) }
      await refresh(outletId, true); setNotice('Table removed. Its QR no longer works.')
    } catch (failure) { setError((failure as Error).message) }
  }
  async function rotateQr(table: Table) {
    if (!window.confirm('Regenerate this table QR? The previous QR will immediately stop working, including any printed copies. You must print and place the new QR at the table.')) return
    setBusy(true); setError('')
    try { const result = await api.post<{ qr_url: string }>(`/api/v1/staff/tables/${table.id}/rotate-qr`, {}); setQr({ url: result.qr_url, label: table.label }); setNotice('QR regenerated. The previous QR no longer works; print the new one.') }
    catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  async function viewQr(table: Table) {
    setBusy(true); setError('')
    try { const result = await api.get<{ qr_url: string }>(`/api/v1/staff/tables/${table.id}/qr`); setQr({ url: result.qr_url, label: table.label }) }
    catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  async function logout() {
    try { await api.post('/api/v1/staff/logout', {}) } finally { setUser(null); setOutlets([]); setOutletId('') }
  }

  if (checking) return <div className="staff-loading"><UtensilsCrossed size={30} /><span>Opening your workspace…</span></div>
  if (!user) return <StaffLogin onLogin={() => void bootstrap()} />

  const nav: { id: Section; label: string; icon: typeof Store }[] = [
    { id: 'overview', label: 'Overview', icon: Store }, { id: 'kitchen', label: 'Kitchen', icon: ChefHat },
    { id: 'tables', label: 'Tables', icon: ClipboardList }, { id: 'menu', label: 'Menu', icon: MenuIcon },
    { id: 'settings', label: 'Settings', icon: Settings2 },
  ]

  return <div className="staff-app"><aside className="staff-sidebar"><div className="staff-sidebar-brand"><div><UtensilsCrossed size={23} /></div><span>DineBridge<small>RESTAURANT PORTAL</small></span></div><div className="staff-sidebar-label">WORKSPACE</div><nav>{nav.map(entry => <button key={entry.id} className={section === entry.id ? 'active' : ''} onClick={() => setSection(entry.id)}><entry.icon size={18} /><span>{entry.label}</span>{entry.id === 'kitchen' && queue.length > 0 && <b>{queue.length}</b>}</button>)}</nav><div className="staff-sidebar-bottom"><div className="staff-user-avatar">{(user.full_name || user.email).slice(0, 1).toUpperCase()}</div><div><strong>{user.full_name || 'Team member'}</strong><small>{user.email}</small></div><button onClick={() => void logout()} aria-label="Sign out"><LogOut size={17} /></button></div></aside>
    <div className="staff-workspace"><header className="staff-topbar"><div><span className="staff-kicker">RESTAURANT OPERATIONS</span><h1>{section === 'overview' ? 'Good service starts here.' : nav.find(entry => entry.id === section)?.label}</h1></div><div className="staff-top-actions"><div className="staff-outlet-identity"><Store size={17} /><span><strong>{outlet?.brand_name || "Restaurant"}</strong><small>{outlet?.name || "Outlet"}</small></span>{outlets.length > 1 && <button onClick={() => setSwitchOutletOpen(true)}>Switch</button>}</div><button className="staff-refresh" onClick={() => void refresh(outletId)} aria-label="Refresh workspace"><RefreshCw size={18} /></button></div></header>
      {!outlet && <div className="staff-empty">No active outlet is assigned to this staff account.</div>}
      {outlet && <main className="staff-main">{error && <div className="staff-toast error" role="alert">{error}<button onClick={() => setError('')} aria-label="Dismiss"><X size={16} /></button></div>}{notice && <div className="staff-toast success" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss"><X size={16} /></button></div>}
        {section === 'overview' && <><div className="staff-overview-head"><p>Keep the dining room moving, one table at a time.</p><span><span className="staff-live-dot" /> Live workspace {lastUpdated && `· Updated ${lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}</span></div><div className="staff-metrics"><div><span className="metric-icon sage"><Store size={20} /></span><small>ACTIVE TABLES</small><strong>{activeTables.length}</strong><span>Guests currently dining</span></div><div><span className="metric-icon peach"><ChefHat size={20} /></span><small>KITCHEN ITEMS</small><strong>{queue.length}</strong><span>Waiting to be prepared or served</span></div><div><span className="metric-icon blue"><Bell size={20} /></span><small>SERVICE REQUESTS</small><strong>{requests.length}</strong><span>Need your attention</span></div><div><span className="metric-icon gold"><ShoppingBag size={20} /></span><small>NEW ORDERS</small><strong>{unseenCount}</strong><span>Not yet acknowledged</span></div></div><div className="staff-two-col"><section className="staff-panel"><div className="staff-panel-head"><div><span className="staff-kicker">RIGHT NOW</span><h2>Tables needing attention</h2></div><button onClick={() => setSection('tables')}>All tables <ArrowRight size={15} /></button></div>{tables.filter(table => table.unseen_orders || table.open_requests).length ? tables.filter(table => table.unseen_orders || table.open_requests).map(table => <button className="attention-row" key={table.id} onClick={() => { setSection('tables'); void openTable(table) }}><span className="table-circle">{table.label}</span><span><strong>{table.label}</strong><small>{table.unseen_orders ? `${table.unseen_orders} new order${table.unseen_orders === 1 ? '' : 's'}` : ''}{table.unseen_orders && table.open_requests ? ' · ' : ''}{table.open_requests ? `${table.open_requests} request${table.open_requests === 1 ? '' : 's'}` : ''}</small></span><ArrowRight size={16} /></button>) : <div className="staff-empty compact">All caught up. The dining room is in good hands.</div>}</section><section className="staff-panel"><div className="staff-panel-head"><div><span className="staff-kicker">UP NEXT</span><h2>Kitchen queue</h2></div><button onClick={() => setSection('kitchen')}>Open kitchen <ArrowRight size={15} /></button></div>{queue.length ? queue.slice(0, 5).map(line => <div className="queue-preview" key={line.line_id}><span className="queue-table">{line.table_label}</span><span><strong>{line.item_name}</strong><small>{line.queued_qty ? 'Waiting to start' : line.preparing_qty ? 'Preparing' : 'Ready to serve'}</small></span><b>×{line.queued_qty + line.preparing_qty + line.ready_qty}</b></div>) : <div className="staff-empty compact">No dishes in the queue right now.</div>}</section></div></>}
        {section === 'kitchen' && <section className="staff-panel"><div className="staff-panel-head"><div><span className="staff-kicker">LIVE ORDERS</span><h2>Kitchen queue</h2></div><span className="staff-muted">Updates every 10 seconds</span></div>{queue.length ? <div className="kitchen-grid">{queue.map(line => <article className="kitchen-card" key={line.line_id}><div className="kitchen-card-head"><span className="queue-table">{line.table_label}</span><span>Order {line.display_ref}</span></div><h3>{line.item_name}</h3><p>{line.variant_name}{line.modifiers?.length ? ` · ${line.modifiers.map(option => option.option_name).join(', ')}` : ''}</p>{line.notes && <div className="kitchen-note">“{line.notes}”</div>}<div className="kitchen-progress"><span>{line.queued_qty} queued</span><span>{line.preparing_qty} preparing</span><span>{line.ready_qty} ready</span></div><div className="kitchen-actions">{line.queued_qty > 0 && <button disabled={busy} onClick={() => void progress(line, 'PREPARING', line.queued_qty)}><ChefHat size={16} /> Start {line.queued_qty}</button>}{line.preparing_qty > 0 && <button disabled={busy} onClick={() => void progress(line, 'READY', line.preparing_qty)}><Check size={16} /> Mark ready</button>}{line.ready_qty > 0 && <button disabled={busy} onClick={() => void progress(line, 'SERVED', line.ready_qty)}><UtensilsCrossed size={16} /> Served</button>}</div></article>)}</div> : <div className="staff-empty"><ChefHat size={32} /><h3>All clear in the kitchen</h3><p>New orders will show up here automatically.</p></div>}</section>}
        {section === 'tables' && <><DiningTables tables={tables} selectedId={selectedTable?.id || null} canManage={canManage} onSelect={table => void openTable(table)} onCreate={createTable} onDelete={deleteTable} onError={setError} />
          {selectedTable && <section className="staff-panel visit-panel"><div className="staff-panel-head"><div><span className="staff-kicker">TABLE DETAILS</span><h2>{selectedTable.label}</h2></div><div className="staff-head-actions">{canManage && <><button disabled={busy} onClick={() => void viewQr(selectedTable)}>View / print QR</button><button disabled={busy} onClick={() => void rotateQr(selectedTable)}>Regenerate QR</button></>}<button onClick={() => { setSelectedTable(null); setDetail(null) }} aria-label="Close table"><X size={18} /></button></div></div>{detail ? <><div className="visit-summary"><div><small>STATUS</small><strong>{detail.reconciliation.status}</strong></div><div><small>ORDERS</small><strong>{detail.reconciliation.order_count}</strong></div><div><small>EFFECTIVE SUBTOTAL</small><strong>{money(detail.reconciliation.effective_subtotal_paise)}</strong></div><div><small>ITEMS OPEN</small><strong>{detail.reconciliation.outstanding_units}</strong></div></div>{detail.orders.map(order => <div className="visit-order" key={order.id}><div><strong>Order {order.display_ref}</strong><small>{new Date(order.placed_at || '').toLocaleString()}</small></div>{order.lines.map(line => <p key={line.id}>{line.quantity} × {line.item_name} · {line.variant_name}</p>)}{!order.seen_at && <button disabled={busy} onClick={() => void action(() => api.post(`/api/v1/staff/orders/${order.id}/seen`, {}), 'Order acknowledged.', reloadDetail)}>Acknowledge order</button>}</div>)}{canBill && <div className="billing-actions">{detail.reconciliation.status === 'OPEN' && <button className="staff-primary" disabled={busy} onClick={() => void action(() => api.post(`/api/v1/staff/visits/${detail.visit_id}/checkout`, {}), 'Checkout started.', reloadDetail)}><CreditCard size={17} /> Start checkout</button>}{detail.reconciliation.status === 'CHECKOUT' && <><button className="staff-secondary" disabled={busy} onClick={() => void action(() => api.post(`/api/v1/staff/visits/${detail.visit_id}/cancel-checkout`, {}), 'Ordering resumed.', reloadDetail)}>Return to ordering</button><form className="billing-form" onSubmit={event => { event.preventDefault(); void action(() => api.post(`/api/v1/staff/visits/${detail.visit_id}/complete-billing`, { external_bill_ref: billRef, external_total_paise: Math.round(Number(billAmount) * 100), payment_method_label: billMethod }), 'Billing completed. Table is ready for the next visit.', async () => { setDetail(null); setSelectedTable(null) }) }}><h3>Complete external POS bill</h3><p>Serve or cancel every item and resolve requests first. The POS remains the payment source of truth.</p><input value={billRef} onChange={event => setBillRef(event.target.value)} placeholder="POS bill reference" required /><input type="number" min="0" step="0.01" value={billAmount} onChange={event => setBillAmount(event.target.value)} placeholder="Total paid (₹)" required /><input value={billMethod} onChange={event => setBillMethod(event.target.value)} placeholder="Payment method" required /><button className="staff-primary" disabled={busy}>Confirm completed bill</button></form></>}</div>}</> : <div className="staff-empty compact">This table has no active visit.</div>}</section>}
          <section className="staff-panel"><div className="staff-panel-head"><div><span className="staff-kicker">GUEST CARE</span><h2>Service requests</h2></div><span className="staff-muted">{requests.length} open</span></div>{requests.length ? requests.map(request => <div className="request-row" key={request.id}><span className="queue-table">{request.table_label}</span><span><strong>{request.kind === 'BILL' ? 'Bill requested' : 'Waiter requested'}</strong><small>{new Date(request.requested_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</small></span><button disabled={busy} onClick={() => void action(() => api.post(`/api/v1/staff/service-requests/${request.id}/resolve`, {}), 'Request resolved.', reloadDetail)}>Resolve</button></div>) : <div className="staff-empty compact">No open service requests.</div>}</section></>}
        {section === 'menu' && (canManage ? <MenuStudio key={outletId} outlet={outlet} catalogue={catalogue} onChanged={() => refresh(outletId, true)} onNotify={(message, kind) => kind === 'error' ? setError(message) : setNotice(message)} /> : <div className="staff-empty">Menu management is available to owners and managers.</div>)}
        {section === 'settings' && (canManage ? <div className="staff-two-col"><section className="staff-panel"><div className="staff-panel-head"><div><span className="staff-kicker">CUSTOMER EXPERIENCE</span><h2>Ordering</h2></div></div><div className="setting-row"><span><strong>Accept new orders</strong><small>Guests can browse the menu even when ordering is paused.</small></span><div className="setting-actions"><button className={`staff-setting-toggle ${pendingOrdering ? 'on' : ''}`} role="switch" aria-checked={pendingOrdering} onClick={() => setPendingOrdering(!pendingOrdering)} disabled={busy}><span /></button><button className="staff-primary" disabled={busy || pendingOrdering === !!config?.ordering_enabled} onClick={() => void action(() => api.patch(`/api/v1/staff/outlets/${outletId}/ordering`, { ordering_enabled: pendingOrdering }), `Ordering ${pendingOrdering ? 'enabled' : 'paused'}.`)}>Save</button></div></div></section><section className="staff-panel"><div className="staff-panel-head"><div><span className="staff-kicker">YOUR BRAND</span><h2>Restaurant identity</h2></div></div><form className="staff-form" onSubmit={event => { event.preventDefault(); void action(() => api.patch(`/api/v1/staff/outlets/${outletId}/branding`, { display_name: brandName, primary_color: primaryColor, accent_color: accentColor }), 'Branding saved.') }}><label>Display name<input value={brandName} onChange={event => setBrandName(event.target.value)} required /></label><div className="staff-form-pair"><label>Primary color<input type="color" value={primaryColor} onChange={event => setPrimaryColor(event.target.value)} /></label><label>Accent color<input type="color" value={accentColor} onChange={event => setAccentColor(event.target.value)} /></label></div><button className="staff-primary" disabled={busy}>Save branding</button></form></section></div> : <div className="staff-empty">Outlet settings are available to owners and managers.</div>)}
      </main>}</div>
    <nav className="staff-mobile-nav">{nav.map(entry => <button key={entry.id} className={section === entry.id ? 'active' : ''} onClick={() => setSection(entry.id)}><entry.icon size={19} /><span>{entry.label}</span></button>)}</nav>
    {switchOutletOpen && <StaffModal title="Choose outlet" onClose={() => setSwitchOutletOpen(false)}><div className="staff-outlet-options">{outlets.map(entry => <button key={entry.id} onClick={() => { setOutletId(entry.id); setSelectedTable(null); setDetail(null); setSwitchOutletOpen(false) }}><strong>{entry.brand_name}</strong><small>{entry.name}</small></button>)}</div></StaffModal>}
    {qr && <div className="staff-qr-backdrop"><div className="staff-qr-modal"><button className="staff-qr-close" onClick={() => setQr(null)} aria-label="Close QR"><X size={19} /></button><div className="staff-qr-print"><div className="staff-qr-logo"><UtensilsCrossed size={18} /> DineBridge</div><h2>{outlet?.brand_name}</h2><p>Scan to order · {qr.label}</p><QRCodeSVG value={qr.url} size={230} level="H" includeMargin /><strong>{qr.label}</strong><small>Keep this code at the table. Regenerate it if it is lost or copied.</small></div><button className="staff-primary" onClick={() => window.print()}>Print table QR</button><p className="staff-qr-hint">You can view and print the current QR again from this table.</p></div></div>}
  </div>
}
