/**
 * PROMETEO Studio · composición de la interfaz.
 * La lógica vive en hooks (useBackend, useDocumentSession, useTransaction);
 * aquí solo se conectan paneles y se resuelven la selección y los atajos.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, ChevronUp, GitCompare, Layers, MessageSquare, ShieldCheck } from 'lucide-react';
import { useBackend } from './hooks/useBackend';
import { useDocumentSession } from './hooks/useDocumentSession';
import { useTransaction, useVerifiedPage } from './hooks/useTransaction';
import { getBackendEndpoint, studioApi } from './api/client';
import { ApiError, isCancellation, normalizeError } from './api/errors';
import type { NodeDetail, OCRObservation } from './types';
import { BootScreen } from './components/BootScreen';
import { Toolbar } from './components/Toolbar';
import { BoardWorkspace } from './components/BoardWorkspace';
import { Outliner } from './components/Outliner';
import { Viewport } from './components/Viewport';
import { Inspector } from './components/Inspector';
import { TransactionTray } from './components/TransactionTray';
import { VerifierPanel } from './components/VerifierPanel';
import { DiffPanel, textChanges } from './components/DiffPanel';
import { AgentPanel, type AgentMessage } from './components/AgentPanel';
import { Welcome } from './components/Welcome';
import { StatusBar } from './components/StatusBar';
import { SearchModal } from './components/SearchModal';
import { UnsavedDialog } from './components/UnsavedDialog';
import { useUnsavedGuard } from './hooks/useUnsavedGuard';
import { useBoardWrites } from './hooks/useBoardWrites';
import { describeBoardUnsaved } from './state/unsaved';
import { flushBoardWrites } from './board/saveQueue';
import { exportarRescateTableros } from './board/rescate';
import { useNativeAutoTest } from './testing/useNativeAutoTest';
import { ErrorNotice, Notice, useResizable } from './components/ui';

type DockTab = 'changes' | 'verification' | 'compare' | 'assistant';

const isEditable = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));

export const App: React.FC = () => {
  const backend = useBackend();
  const [workspaceMode, setWorkspaceMode] = useState<'pdf' | 'board'>('pdf');
  // Mantén montada la interfaz si el motor cae después de haber arrancado: el tablero es local.
  const [everReady, setEverReady] = useState(false);
  const isReady = backend.phase === 'BACKEND_READY' || backend.phase === 'DEGRADED';
  useEffect(() => {
    if (isReady) setEverReady(true);
  }, [isReady]);
  if (workspaceMode === 'pdf' && !everReady && (backend.phase === 'FAILED' || backend.phase === 'STARTING')) {
    return <BootScreen backend={backend} onRetry={backend.retry} onOpenBoard={() => setWorkspaceMode('board')} />;
  }
  return <Studio backend={backend} workspaceMode={workspaceMode} setWorkspaceMode={setWorkspaceMode} />;
};

const Studio: React.FC<{
  backend: ReturnType<typeof useBackend>;
  workspaceMode: 'pdf' | 'board';
  setWorkspaceMode: (mode: 'pdf' | 'board') => void;
}> = ({ backend, workspaceMode, setWorkspaceMode }) => {
  const endpoint = useMemo(() => getBackendEndpoint(), []);
  const ready = backend.phase === 'BACKEND_READY';
  const pdfBackendAvailable = ready || backend.phase === 'DEGRADED';
  const docs = useDocumentSession(pdfBackendAvailable);
  const sessionId = docs.doc?.sessionId ?? null;
  const { tx, busy, stageText, stageRaster, remove, clear, verify, save, markDownloaded, reveal, refresh, dismissError, undo, redo, canUndo, canRedo } = useTransaction(sessionId);

  const [uiMode, setUiMode] = useState<'user' | 'technical'>('user');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedOcr, setSelectedOcr] = useState<OCRObservation | null>(null);
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [nodeLoading, setNodeLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'original' | 'compare'>('original');
  const [dockTab, setDockTab] = useState<DockTab>('changes');
  const [dockOpen, setDockOpen] = useState(true);
  const [leftOpen, setLeftOpen] = useState(() => window.innerWidth > 1000);
  const [rightOpen, setRightOpen] = useState(() => window.innerWidth > 1000);
  const [narrowPanels, setNarrowPanels] = useState(() => window.innerWidth <= 1000);
  const wasNarrow = useRef(window.innerWidth <= 1000);
  const [dockHeight, setDockHeight] = useState(() => Math.round(Math.max(170, Math.min(260, window.innerHeight * 0.3))));
  const [searchOpen, setSearchOpen] = useState(false);

  // Al entrar en una ventana estrecha los paneles se pliegan para no tapar el visor;
  // al volver a una ancha se recuperan. Las palancas siguen disponibles en ambos casos.
  useEffect(() => {
    const onResize = () => {
      const narrow = window.innerWidth <= 1000;
      if (narrow === wasNarrow.current) return;
      wasNarrow.current = narrow;
      setNarrowPanels(narrow);
      setLeftOpen(!narrow);
      setRightOpen(!narrow);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  const [agentMessages, setAgentMessages] = useState<AgentMessage[]>([]);
  const [agentThinking, setAgentThinking] = useState(false);
  const [sessionLost, setSessionLost] = useState<ApiError | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const left = useResizable(280, 200, 480);
  const right = useResizable(340, 280, 520, true);

  // Al cambiar de documento se reinicia la selección y la vista.
  useEffect(() => {
    setSelectedNodeId(null);
    setSelectedOcr(null);
    setNodeDetail(null);
    setViewMode('original');
    setAgentMessages([]);
    setDockTab('changes');
    if (sessionId) setSessionLost(null);
  }, [sessionId]);

  // Muestra automática solo si el host la pidió (pruebas nativas).
  const autoOpened = useRef(false);
  const { samples, openSample } = docs;
  useEffect(() => {
    const key = endpoint.autoOpenSample;
    if (!autoOpened.current && key && ready && !docs.restoring && !docs.doc && samples.some((s) => s.key === key)) {
      autoOpened.current = true;
      openSample(key);
    }
  }, [endpoint.autoOpenSample, ready, samples, openSample, docs.restoring, docs.doc]);

  // Detalle del nodo seleccionado (cancelable).
  useEffect(() => {
    if (!sessionId || !selectedNodeId) {
      setNodeDetail(null);
      return;
    }
    const ctrl = new AbortController();
    setNodeLoading(true);
    studioApi
      .getNode(sessionId, selectedNodeId, ctrl.signal)
      .then(setNodeDetail)
      .catch((err) => {
        const e = normalizeError(err);
        if (!isCancellation(e)) setNodeDetail(null);
      })
      .finally(() => setNodeLoading(false));
    return () => ctrl.abort();
  }, [sessionId, selectedNodeId]);

  // Tras una reconexión, comprobar que la sesión sigue existiendo en el motor.
  const prevPhase = useRef(backend.phase);
  useEffect(() => {
    if (prevPhase.current === 'DISCONNECTED' && backend.phase === 'BACKEND_READY' && sessionId) {
      studioApi.getTransaction(sessionId).catch((err) => {
        const e = normalizeError(err, 'SESSION');
        if (e.code === 'SESSION_NOT_FOUND') {
          setSessionLost(e);
          docs.resetDocument();
        }
      });
    }
    prevPhase.current = backend.phase;
  }, [backend.phase, sessionId, docs]);

  const stagedNodeIds = useMemo(() => new Set(tx.ops.map((o) => o.node_id)), [tx.ops]);
  const compare = useVerifiedPage(sessionId, docs.currentPage, tx.phase === 'VERIFIED' && viewMode === 'compare', tx.lastResponse?.output_sha256 ?? null);

  const selectNode = useCallback(
    (id: string, page?: number) => {
      setSelectedOcr(null);
      setSelectedNodeId(id);
      if (typeof page === 'number') docs.setCurrentPage(page);
    },
    [docs],
  );
  const selectOcr = useCallback(
    (obs: OCRObservation) => {
      setSelectedNodeId(null);
      setSelectedOcr(obs);
      docs.setCurrentPage(obs.page);
      if (!docs.ocrVisible) docs.setOcrVisible(true);
    },
    [docs],
  );

  const handleVerify = useCallback(async () => {
    setDockOpen(true);
    setDockTab('verification');
    const res = await verify();
    if (res?.ok) {
      setViewMode('compare');
    } else if (res) {
      // El motivo del fallo vive en «Verificación»: se le da altura suficiente para leerlo.
      setDockHeight((height) => Math.min(560, Math.max(height, Math.min(window.innerHeight - 170, 380))));
    }
  }, [verify]);

  /** Guarda la copia verificada (escritorio: Descargas › PROMETEO; navegador: descarga). true si quedó guardada. */
  const saveCopy = useCallback(async (): Promise<boolean> => {
    if (!sessionId) return false;
    if (endpoint.isDesktop) return Boolean(await save());
    try {
      markDownloaded(await studioApi.downloadVerifiedPdf(sessionId));
      return true;
    } catch {
      return false; // en web el navegador informa del fallo de descarga
    }
  }, [endpoint.isDesktop, markDownloaded, save, sessionId]);

  const handleSave = useCallback(async () => {
    await saveCopy();
  }, [saveCopy]);

  // Nada se pierde en silencio: cerrar o abrir otro documento con trabajo sin guardar pregunta antes.
  const boardWrites = useBoardWrites();
  const boardWork = useMemo(() => describeBoardUnsaved(boardWrites.pending), [boardWrites.pending]);
  // Con cambios del tablero pendientes, «Guardar» guarda el tablero; si no, la copia PDF como antes.
  const saveAll = useCallback(async () => (boardWork ? flushBoardWrites() : saveCopy()), [boardWork, saveCopy]);
  const unsaved = useUnsavedGuard(tx, 'Descargas', saveAll, boardWork, {
    flush: boardWork ? flushBoardWrites : undefined,
    onExport: boardWork ? () => { void exportarRescateTableros(); } : undefined,
  });
  const openSampleGuarded = useCallback((key: string) => unsaved.guard('open', () => void docs.openSample(key)), [unsaved, docs]);
  const openFileGuarded = useCallback((file: File) => unsaved.guard('open', () => void docs.openFile(file)), [unsaved, docs]);

  const retryLoadGuarded = useCallback(() => unsaved.guard('open', () => void docs.retryLoad()), [unsaved, docs]);

  // Solo pruebas nativas (PROMETEO_AUTOTEST); inactivo en un arranque normal.
  useNativeAutoTest({
    scenario: endpoint.autoTest,
    autoOpenSample: endpoint.autoOpenSample,
    openedSample: docs.doc?.source.kind === 'sample' ? docs.doc.source.key : null,
    docReady: docs.phase === 'READY' && Boolean(docs.doc),
    nodesOnPage: docs.nodesOnPage,
    restored: docs.restored,
    txPhase: tx.phase,
    stageText,
    verify,
  });

  // Escritorio: sin menú contextual del WebView («Recargar» descartaría la sesión) salvo en campos
  // de texto, donde copiar y pegar sí es útil.
  useEffect(() => {
    if (!endpoint.isDesktop) return;
    const onContext = (e: MouseEvent) => {
      if (!isEditable(e.target)) e.preventDefault();
    };
    window.addEventListener('contextmenu', onContext);
    return () => window.removeEventListener('contextmenu', onContext);
  }, [endpoint.isDesktop]);

  const sendAgent = useCallback(
    async (text: string) => {
      if (!sessionId) return;
      setAgentMessages((m) => [...m, { from: 'user', text }]);
      setAgentThinking(true);
      try {
        const res = await studioApi.sendAgentMessage(sessionId, text);
        setAgentMessages((m) => [...m, { from: 'assistant', text: String(res.reply?.content ?? ''), status: res.reply?.status }]);
        if (res.reply?.status === 'WAITING_HUMAN_APPROVAL') await refresh();
      } catch (err) {
        const e = normalizeError(err);
        setAgentMessages((m) => [...m, { from: 'assistant', text: `No se pudo procesar: ${e.message}` }]);
      } finally {
        setAgentThinking(false);
      }
    },
    [sessionId, refresh],
  );

  // Atajos: ⌘F busca; RePág/AvPág cambian de página fuera de campos de texto; Esc limpia la selección.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // En el tablero el teclado es del tablero: los atajos PDF no deben actuar sobre un documento oculto.
      if (workspaceMode === 'board') return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'f' && sessionId) {
        e.preventDefault();
        setSearchOpen(true);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && !isEditable(e.target)) {
        e.preventDefault();
        if (e.shiftKey) void redo();
        else void undo();
        return;
      }
      if (isEditable(e.target) || searchOpen) return;
      if (e.key === 'PageDown') docs.stepPage(1);
      else if (e.key === 'PageUp') docs.stepPage(-1);
      else if (e.key === 'Escape') {
        setSelectedNodeId(null);
        setSelectedOcr(null);
      } else return;
      e.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [docs, redo, searchOpen, sessionId, undo, workspaceMode]);

  const workspaceError =
    backend.phase === 'DEGRADED' ? backend.error ?? new ApiError({ code: 'WORKSPACE_UNAVAILABLE', message: 'Motor degradado.' }) : null;
  const boardEngineMessage =
    backend.phase === 'FAILED'
      ? 'El motor PDF no está disponible. Tus tableros y proyectos locales siguen funcionando.'
      : backend.phase === 'DISCONNECTED'
        ? 'Se perdió la conexión con el motor PDF. El tablero local sigue disponible.'
        : backend.phase === 'STARTING'
          ? 'El motor PDF se está iniciando. Puedes seguir trabajando en el tablero local.'
          : backend.phase === 'DEGRADED'
            ? 'El motor PDF está en modo degradado. El tablero local sigue disponible.'
            : undefined;
  const loading = docs.phase === 'DOCUMENT_LOADING';
  const startDock = useRef({ y: 0, h: 0 });

  if (workspaceMode === 'board') {
    return (
      <>
        <BoardWorkspace
          onBack={() => setWorkspaceMode('pdf')}
          locked={Boolean(unsaved.dialog)}
          engineMessage={boardEngineMessage}
          onRetryEngine={backend.retry}
          pdfReferenceSource={docs.doc ? {
            filename: docs.doc.filename,
            sha256: docs.doc.summary.source_sha256,
            page: docs.currentPage + 1,
          } : null}
          onOpenPdfReference={(reference) => {
            if (!docs.doc || docs.doc.summary.source_sha256.toLowerCase() !== reference.sourceSha256) return false;
            docs.setCurrentPage(reference.page - 1);
            setWorkspaceMode('pdf');
            return true;
          }}
        />
        {unsaved.dialog && createPortal(<UnsavedDialog {...unsaved.dialog} />, document.body)}
      </>
    );
  }

  return (
    <div className="app" inert={unsaved.dialog ? true : undefined}>
      <Toolbar
        doc={docs.doc}
        pageCount={docs.pageCount}
        txPhase={tx.phase}
        stagedCount={tx.ops.length}
        samples={docs.samples}
        busy={loading || busy !== 'none'}
        uiMode={uiMode}
        onOpenSample={openSampleGuarded}
        onOpenFile={openFileGuarded}
        onToggleMode={() => setUiMode((m) => (m === 'user' ? 'technical' : 'user'))}
        onSearch={() => setSearchOpen(true)}
        onOpenBoard={() => unsaved.guard('open', () => setWorkspaceMode('board'))}
        leftOpen={leftOpen}
        rightOpen={rightOpen}
        onToggleLeft={() => setLeftOpen((open) => !open)}
        onToggleRight={() => setRightOpen((open) => !open)}
      />

      <div className="app-notice-area" aria-live="polite">
        {backend.phase === 'DISCONNECTED' && backend.error && <ErrorNotice error={backend.error} onRetry={backend.retry} />}
        {backend.phase === 'FAILED' && backend.error && <ErrorNotice error={backend.error} onRetry={backend.retry} />}
        {sessionLost && (
          <Notice tone="warn" title="El documento se cerró" onDismiss={() => setSessionLost(null)}>
            <p className="notice-text">El motor se reinició y la sesión anterior ya no existe. Vuelve a abrir el documento.</p>
          </Notice>
        )}
        {docs.restored && (
          <Notice tone="ok" title="Sesión recuperada" onDismiss={docs.dismissRestored}>
            <p className="notice-text">
              La interfaz se recargó y se recuperó «{docs.doc?.filename}» con sus cambios.
              {tx.phase === 'VERIFIED' && !tx.saved ? ' La copia verificada sigue disponible: puedes guardarla en Verificación.' : ''}
            </p>
          </Notice>
        )}
        {backend.phase === 'STARTING' && (
          <Notice tone="info" title="Reconectando con el motor…">
            <p className="notice-text">Tu documento sigue abierto mientras se recupera la conexión.</p>
          </Notice>
        )}
        {docs.doc && docs.loadError && <ErrorNotice error={docs.loadError} onRetry={retryLoadGuarded} onDismiss={docs.dismissLoadError} />}
        {tx.error && (
          <ErrorNotice
            error={tx.error}
            onDismiss={dismissError}
            reassurance={tx.lastResponse?.original_unchanged ? 'Tu original no cambió: el motor comprobó su huella SHA-256.' : undefined}
          />
        )}
      </div>

      {!docs.doc ? (
        <main className="welcome-stage" aria-label="Inicio">
          <Welcome
            samples={docs.samples}
            samplesError={docs.samplesError}
            onRetrySamples={docs.retrySamples}
            loading={loading}
            loadingLabel={docs.loadingLabel}
            error={docs.loadError}
            workspaceError={workspaceError}
            onOpenFile={() => fileInput.current?.click()}
            onOpenSample={docs.openSample}
            onRetry={docs.retryLoad}
            onDismiss={docs.dismissLoadError}
          />
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf,.pdf"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) docs.openFile(f);
              e.target.value = '';
            }}
          />
        </main>
      ) : (
        <>
      <main
        className={`workspace ${leftOpen ? '' : 'left-collapsed'} ${rightOpen ? '' : 'right-collapsed'}`}
        style={{ ['--left-w' as string]: `${left.size}px`, ['--right-w' as string]: `${right.size}px` }}
      >
        {narrowPanels && (leftOpen || rightOpen) && (
          <button
            type="button"
            className="panel-scrim"
            aria-label="Cerrar los paneles abiertos"
            onClick={() => { setLeftOpen(false); setRightOpen(false); }}
          />
        )}
        <Outliner
          pageCount={docs.pageCount}
          pageNodes={docs.pageNodes}
          pageLoading={docs.pageNodesLoading}
          selectedNodeId={selectedNodeId}
          stagedNodeIds={stagedNodeIds}
          currentPage={docs.currentPage}
          loading={loading}
          uiMode={uiMode}
          onSelectNode={selectNode}
          onNavigatePage={docs.setCurrentPage}
        />
        <div {...left.handleProps} className={`${left.handleProps.className} resizer-left`} aria-label="Ancho del panel Contenido" />

          <Viewport
            render={docs.render}
            onRetryRender={docs.retryRender}
            nodesOnPage={docs.nodesOnPage}
            selectedNodeId={selectedNodeId}
            stagedNodeIds={stagedNodeIds}
            onSelectNode={(id) => selectNode(id)}
            currentPage={docs.currentPage}
            pageCount={docs.pageCount}
            onPageChange={docs.setCurrentPage}
            onPageStep={docs.stepPage}
            ocr={docs.ocr}
            ocrVisible={docs.ocrVisible}
            isRaster={docs.doc.isRaster}
            onToggleOcr={() => docs.setOcrVisible(!docs.ocrVisible)}
            onRetryOcr={docs.retryOcr}
            selectedOcrId={selectedOcr?.id ?? null}
            onSelectOcr={selectOcr}
            compare={{ available: tx.phase === 'VERIFIED', data: compare.data, error: compare.error }}
            viewMode={tx.phase === 'VERIFIED' ? viewMode : 'original'}
            onViewMode={setViewMode}
            uiMode={uiMode}
            showStagedTags={tx.phase !== 'VERIFIED' && viewMode !== 'compare'}
          />

        <div {...right.handleProps} className={`${right.handleProps.className} resizer-right`} aria-label="Ancho del Inspector" />
        <Inspector
          sessionId={sessionId}
          node={nodeDetail}
          nodeLoading={nodeLoading}
          ocrObservation={selectedOcr}
          isStaged={!!selectedNodeId && stagedNodeIds.has(selectedNodeId)}
          txPhase={tx.phase}
          busy={busy !== 'none'}
          uiMode={uiMode}
          onStageText={async (id, text) => {
            await stageText(id, text);
            setDockOpen(true);
            setDockTab('changes');
          }}
          onStageRaster={async (page, obsId, text) => {
            await stageRaster(page, obsId, text);
            setDockOpen(true);
            setDockTab('changes');
          }}
        />
      </main>

      <section className="dock" style={{ height: dockOpen ? dockHeight : 42 }} aria-label="Cambios y verificación">
        {dockOpen && (
          <div
            className="resizer resizer-h"
            role="separator"
            aria-orientation="horizontal"
            aria-label="Altura del panel inferior"
            tabIndex={0}
            onPointerDown={(e) => {
              startDock.current = { y: e.clientY, h: dockHeight };
              (e.target as HTMLElement).setPointerCapture(e.pointerId);
            }}
            onPointerMove={(e) => {
              if (!(e.buttons & 1)) return;
              setDockHeight(Math.max(160, Math.min(560, startDock.current.h - (e.clientY - startDock.current.y))));
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowUp') setDockHeight((h) => Math.min(560, h + 24));
              else if (e.key === 'ArrowDown') setDockHeight((h) => Math.max(160, h - 24));
            }}
          />
        )}
        <div className="dock-bar">
          <div className="tabs" role="tablist" aria-label="Paneles">
            {(
              [
                { id: 'changes', icon: <Layers size={14} />, label: 'Cambios', count: tx.ops.length },
                { id: 'verification', icon: <ShieldCheck size={14} />, label: 'Verificación', count: null },
                { id: 'compare', icon: <GitCompare size={14} />, label: 'Diferencias', count: tx.diff ? (uiMode === 'technical' ? tx.diff.summary.changed_count : textChanges(tx.diff).length) : null },
                { id: 'assistant', icon: <MessageSquare size={14} />, label: 'Asistente', count: null },
              ] as Array<{ id: DockTab; icon: React.ReactNode; label: string; count: number | null }>
            ).map((t) => (
              <button
                key={t.id}
                role="tab"
                id={`tab-${t.id}`}
                aria-controls="dock-panel"
                aria-selected={dockTab === t.id}
                className="tab"
                onClick={() => {
                  setDockTab(t.id);
                  setDockOpen(true);
                }}
              >
                <span aria-hidden="true">{t.icon}</span>
                {t.label}
                {t.count !== null && t.count > 0 && <span className="count">{t.count}</span>}
              </button>
            ))}
          </div>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setDockOpen((v) => !v)} aria-label={dockOpen ? 'Contraer panel inferior' : 'Expandir panel inferior'} aria-expanded={dockOpen}>
            {dockOpen ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
        </div>
        {dockOpen && (
          <div className="dock-body" role="tabpanel" id="dock-panel" aria-labelledby={`tab-${dockTab}`}>
            {dockTab === 'changes' && (
              <TransactionTray ops={tx.ops} phase={tx.phase} verifying={busy === 'verifying'} uiMode={uiMode} onRemove={remove} onClear={clear} onVerify={handleVerify} onUndo={() => void undo()} onRedo={() => void redo()} canUndo={canUndo} canRedo={canRedo} />
            )}
            {dockTab === 'verification' && (
              <VerifierPanel
                response={tx.lastResponse}
                phase={tx.phase}
                saved={tx.saved}
                saving={busy === 'saving'}
                canReveal={endpoint.isDesktop}
                uiMode={uiMode}
                onSave={handleSave}
                onReveal={reveal}
                saveLabel={endpoint.isDesktop ? 'Guardar copia en Descargas' : 'Descargar copia verificada'}
              />
            )}
            {dockTab === 'compare' && <DiffPanel diff={tx.diff} uiMode={uiMode} onSelectNode={(id, page) => selectNode(id, page)} />}
            {dockTab === 'assistant' && <AgentPanel messages={agentMessages} thinking={agentThinking} disabled={!sessionId} onSend={sendAgent} />}
          </div>
        )}
      </section>

        </>
      )}

      <StatusBar phase={backend.phase} version={backend.health?.version} ocrAvailable={backend.health?.ocr_available} isDesktop={endpoint.isDesktop} />

      {searchOpen && sessionId && docs.doc && (
        <SearchModal
          sessionId={sessionId}
          isRaster={docs.doc.isRaster}
          onClose={() => setSearchOpen(false)}
          onPickNode={(id, page) => selectNode(id, page)}
          onPickOcr={selectOcr}
        />
      )}

      {unsaved.dialog && createPortal(<UnsavedDialog {...unsaved.dialog} />, document.body)}
    </div>
  );
};

export default App;
