import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft,
  BookOpen,
  FolderPlus,
  Magnet,
  Download,
  Eye,
  ImagePlus,
  Library,
  Link2,
  Plus,
  Search,
  StickyNote,
  Trash2,
  Undo2,
  Redo2,
  Upload,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import {
  boardFilename,
  boardToMarkdown,
  cloneBoardForImport,
  createBoard,
  isSafeExternalUrl,
  makeBoardExport,
  markdownToBoard,
  MAX_MEDIA_BYTES,
  newBoardId,
  parseBoardImport,
  type BoardCard,
  type BoardDocument,
  type BoardMedia,
} from '../board/model';
import { fitBoardCamera, zoomAtPoint, screenToWorld } from '../board/camera';
import { alignCards, distributeCards, snapPosition, type Alignment, type CardSize, type DistributionAxis } from '../board/geometry';
import {
  cardsInsideFrame,
  detachCardFromFrames,
  FRAME_MIN_SIZE,
  readFrameData,
  rectFromPoints,
  removeFrameKeepingChildren,
  setFrameView,
  type FrameRect,
  type FrameView,
} from '../board/frames';
import { emptyBoardHistory, recordBoardChange, redoBoardChange, undoBoardChange, type BoardHistory } from '../board/history';
import { agregarImagenDesdeUrl, importarBiblioteca } from '../board/referentes/biblioteca';
import { construirZipObsidian, notasObsidian } from '../board/referentes/historial';
import { aceptarLectura } from '../board/referentes/mirar';
import { leerReferente, type Lectura } from '../board/referentes/model';
import { loadBoardWorkspace } from '../board/storage';
import { BoardCardContent } from '../board/tools/CardView';
import { BoardToolMenu } from '../board/tools/menu';
import { getBoardTool, listBoardTools } from '../board/tools/registry';
import { EntropiaVista } from '../board/tools/entropiaVista';
import {
  esMarcoEntropia,
  leerEntropia,
  nuevaSemilla,
  tirarEntropia,
  type EntropiaDatos,
  type FuenteEntropia,
} from '../board/vanguardia/entropia';
import { gustosVacios, importarGustosParciales, like, nope, type Gustos } from '../board/vanguardia/gustos';
import { crearMarcoManifiesto, pedirManifiesto, seleccionarSemana } from '../board/vanguardia/manifiesto';
import { enqueueBoardSave, flushBoardWrites, removeBoardFromStore, rememberActiveBoard } from '../board/saveQueue';
import { publishFrameToDirectory } from '../board/publicar';
import {
  createPdfReference,
  projectToMarkdown,
  type BoardProject,
  type PdfReference,
  type PdfReferenceSource,
} from '../board/projectModel';
import {
  assignBoardToProject,
  createProject,
  deletePdfReference,
  loadProjectWorkspace,
  removeBoardProjectLink,
  savePdfReference,
  saveProjectGustos,
  setActiveProject,
} from '../board/projectStorage';
import { useBoardWrites } from '../hooks/useBoardWrites';
import { MirarDialog } from './MirarDialog';
import { ArchivoView } from './ArchivoView';
import { MuroView } from './MuroView';
import { MesaView } from './MesaView';
import './board.css';

interface BoardWorkspaceProps {
  onBack: () => void;
  /** Con un diálogo de cierre abierto el tablero no recibe interacción. */
  locked?: boolean;
  engineMessage?: string;
  onRetryEngine?: () => void;
  pdfReferenceSource?: PdfReferenceSource | null;
  onOpenPdfReference?: (reference: PdfReference) => boolean;
}

const GRID_SIZE = 24;
const COLORS: Array<BoardCard['color']> = ['paper', 'sand', 'sage', 'rose'];

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => (typeof reader.result === 'string' ? resolve(reader.result) : reject(new Error('No se pudo leer el archivo.')));
    reader.onerror = () => reject(new Error('No se pudo leer el archivo.'));
    reader.readAsDataURL(file);
  });
}

function downloadText(filename: string, content: string, mimeType: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function cardCenter(card: BoardCard): { x: number; y: number } {
  return { x: card.x + card.width / 2, y: card.y + 100 };
}

export const BoardWorkspace: React.FC<BoardWorkspaceProps> = ({
  onBack,
  locked = false,
  engineMessage,
  onRetryEngine,
  pdfReferenceSource = null,
  onOpenPdfReference,
}) => {
  const [boards, setBoards] = useState<BoardDocument[]>([]);
  const [activeBoardId, setActiveBoardId] = useState('');
  const [projects, setProjects] = useState<BoardProject[]>([]);
  const [projectIdByBoardId, setProjectIdByBoardId] = useState<Map<string, string>>(() => new Map());
  const [activeProjectId, setActiveProjectId] = useState('');
  const [projectReferences, setProjectReferences] = useState<PdfReference[]>([]);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [projectLoadAttempt, setProjectLoadAttempt] = useState(0);
  const [projectDialog, setProjectDialog] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [pdfReferenceDialog, setPdfReferenceDialog] = useState(false);
  const [pdfReferenceQuote, setPdfReferenceQuote] = useState('');
  const [pdfReferenceNote, setPdfReferenceNote] = useState('');
  const [referencesOpen, setReferencesOpen] = useState(false);
  /** Ritual «Volver a mirar»: propuestas que aún no tocan el referente. */
  const [mirarOpen, setMirarOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const writes = useBoardWrites();
  const saveState = writes.error ? 'error' : writes.pending > 0 ? 'saving' : 'saved';
  const [loadError, setLoadError] = useState<string | null>(null);
  const storageError = loadError ?? writes.error;
  const [selectedCardIds, setSelectedCardIds] = useState<string[]>([]);
  const [connectMode, setConnectMode] = useState(false);
  const [connectFromId, setConnectFromId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [linkDialog, setLinkDialog] = useState(false);
  const [linkTitle, setLinkTitle] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkError, setLinkError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [snapEnabled, setSnapEnabled] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [viewportSize, setViewportSize] = useState({ width: 0, height: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);
  const panDrag = useRef<{ pointerId: number; x: number; y: number; panX: number; panY: number } | null>(null);
  const cardDrag = useRef<{ pointerId: number; boardId: string; ids: string[]; x: number; y: number; positions: Map<string, { x: number; y: number }>; startBoard: BoardDocument; gesture: string; moved: boolean } | null>(null);
  /** Herramienta de marco elegida en el menú: el siguiente arrastre dibuja el rectángulo. */
  const [frameToolId, setFrameToolId] = useState<string | null>(null);
  const [frameDraft, setFrameDraft] = useState<FrameRect | null>(null);
  const frameDraw = useRef<{ pointerId: number; start: { x: number; y: number } } | null>(null);
  /** Marco abierto a pantalla completa en la vista Archivo; Esc vuelve a la pizarra. */
  const [archiveFullscreenId, setArchiveFullscreenId] = useState<string | null>(null);
  /** Marco cuya publicación local se está escribiendo (bloquea el botón mientras dura). */
  const [publishingFrameId, setPublishingFrameId] = useState<string | null>(null);
  /** El manifiesto semanal espera al motor local; el botón no se dispara dos veces. */
  const [manifesting, setManifesting] = useState(false);
  const [boardHistories, setBoardHistories] = useState<Record<string, BoardHistory>>({});
  /** Un clic que llega después de arrastrar o de un gesto con modificador no debe cambiar la selección otra vez. */
  const suppressCardClick = useRef(false);
  /** El clic posterior a dibujar un marco no debe vaciar la selección recién creada. */
  const suppressViewportClick = useRef(false);
  /** Cada salida de un campo de texto cierra el grupo de deshacer de esa escritura. */
  const textSession = useRef(0);
  const closeTextGroup = () => {
    textSession.current += 1;
  };
  const initializedCamera = useRef(false);
  const previousBoardId = useRef('');
  const importInput = useRef<HTMLInputElement>(null);
  const mediaInput = useRef<HTMLInputElement>(null);
  const gustosInput = useRef<HTMLInputElement>(null);
  /** Referente bajo el puntero: una URL de imagen pegada cae en él. */
  const hoveredReferenteId = useRef<string | null>(null);

  const projectBoards = activeProjectId
    ? boards.filter((board) => projectIdByBoardId.get(board.id) === activeProjectId)
    : boards;
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? null;
  const activeProjectReferences = projectReferences.filter((reference) => reference.projectId === activeProjectId);
  const activeBoard = projectBoards.find((board) => board.id === activeBoardId) ?? projectBoards[0] ?? null;
  const selectedCards = activeBoard?.cards.filter((card) => selectedCardIds.includes(card.id)) ?? [];
  const selectedCard = selectedCards.length === 1 ? selectedCards[0] : null;
  const activeHistory = activeBoard ? boardHistories[activeBoard.id] ?? emptyBoardHistory() : emptyBoardHistory();
  const canUndo = activeHistory.undo.length > 0;
  const canRedo = activeHistory.redo.length > 0;

  const cardsById = useMemo(() => new Map((activeBoard?.cards ?? []).map((card) => [card.id, card])), [activeBoard]);
  /** Hijos que ya se pintan dentro de un marco con vista propia: no se dibujan dos veces. */
  const framedChildIds = useMemo(() => {
    const ids = new Set<string>();
    for (const card of activeBoard?.cards ?? []) {
      if (card.type !== 'marco' || readFrameData(card).vista === 'libre') continue;
      for (const id of readFrameData(card).hijos) ids.add(id);
    }
    return ids;
  }, [activeBoard]);
  const archiveFullscreenFrame = archiveFullscreenId
    ? activeBoard?.cards.find((card) => card.id === archiveFullscreenId && card.type === 'marco') ?? null
    : null;

  /** Referentes de todo el proyecto: son las fuentes posibles de una tirada de Entropía. */
  const fuentesEntropia = useMemo<FuenteEntropia[]>(() => {
    const sourceBoards = projectBoards.length ? projectBoards : activeBoard ? [activeBoard] : [];
    const vistas = new Set<string>();
    const fuentes: FuenteEntropia[] = [];
    for (const board of sourceBoards) {
      for (const card of board.cards) {
        if (card.type !== 'referente' || vistas.has(card.id)) continue;
        vistas.add(card.id);
        const referente = leerReferente(card);
        const imagen = referente.imagenes[0];
        fuentes.push({
          id: card.id,
          nombre: referente.nombre || card.title || 'Referente sin nombre',
          etiquetas: referente.etiquetas,
          ...(imagen ? { imagen: { src: imagen.dataUrl, nombre: imagen.name } } : {}),
        });
      }
    }
    return fuentes;
  }, [projectBoards, activeBoard]);

  const leaveBoard = async () => {
    // Salir con cambios que no están confirmados en el almacenamiento sería perderlos: se queda y se explica.
    const saved = await flushBoardWrites();
    if (!saved) {
      setNotice('No se pudo guardar el tablero. Tus cambios siguen aquí: reintenta o exporta una copia antes de salir.');
      return;
    }
    onBack();
  };

  useEffect(() => {
    let current = true;
    loadBoardWorkspace()
      .then((snapshot) => {
        if (!current) return;
        if (snapshot.boards.length) {
          setBoards(snapshot.boards);
          setActiveBoardId(snapshot.activeBoardId ?? snapshot.boards[0].id);
        } else {
          const first = createBoard('Mi tablero');
          setBoards([first]);
          setActiveBoardId(first.id);
          enqueueBoardSave(first, { immediate: true });
        }
        if (snapshot.skipped.length) {
          const count = snapshot.skipped.length;
          setNotice(`${count === 1 ? 'Un tablero no se pudo abrir' : `${count} tableros no se pudieron abrir`} y se conserva sin cambios: ${snapshot.skipped[0].reason}`);
        }
        setLoaded(true);
      })
      .catch((error: unknown) => {
        if (!current) return;
        setLoadError(error instanceof Error ? error.message : 'El almacenamiento local no está disponible.');
        const first = createBoard('Mi tablero');
        setBoards([first]);
        setActiveBoardId(first.id);
        setLoaded(true);
      });
    return () => {
      current = false;
    };
  }, []);

  const projectBoardIds = useMemo(() => boards.map((board) => board.id).sort(), [boards]);
  const projectBoardSignature = JSON.stringify(projectBoardIds);
  const loadedProjectBoardSignature = useRef('');

  // Proyectos y referencias viven en una base aditiva separada: los registros existentes de tableros no se reescriben.
  useEffect(() => {
    if (!loaded || !projectBoardSignature || loadedProjectBoardSignature.current === projectBoardSignature) return;
    loadedProjectBoardSignature.current = projectBoardSignature;
    let current = true;
    loadProjectWorkspace(projectBoardIds)
      .then((workspace) => {
        if (!current) return;
        setProjects(workspace.projects);
        setProjectIdByBoardId(workspace.projectIdByBoardId);
        setActiveProjectId(workspace.activeProjectId);
        setProjectReferences(workspace.references);
        const selected = boards.find((board) =>
          board.id === activeBoardId && workspace.projectIdByBoardId.get(board.id) === workspace.activeProjectId,
        ) ?? boards.find((board) => workspace.projectIdByBoardId.get(board.id) === workspace.activeProjectId);
        if (selected) setActiveBoardId(selected.id);
        setProjectError(null);
        if (workspace.skipped.length) {
          const first = workspace.skipped[0];
          setNotice(`${workspace.skipped.length === 1 ? 'Un registro de proyecto no se pudo abrir' : `${workspace.skipped.length} registros de proyecto no se pudieron abrir`} y se conservan sin cambios: ${first.reason}`);
        } else if (workspace.migration.linkedExistingBoards > 0) {
          const count = workspace.migration.linkedExistingBoards;
          setNotice(`${count === 1 ? 'Tu tablero existente quedó' : `Tus ${count} tableros existentes quedaron`} organizado${count === 1 ? '' : 's'} en Proyecto general, sin reescribir su contenido.`);
        }
      })
      .catch((error: unknown) => {
        if (!current) return;
        loadedProjectBoardSignature.current = '';
        setProjectError(error instanceof Error ? error.message : 'No se pudieron abrir los proyectos locales.');
        setActiveProjectId('');
        setProjectIdByBoardId(new Map());
      });
    return () => {
      current = false;
    };
  }, [activeBoardId, boards, loaded, projectBoardIds, projectBoardSignature, projectLoadAttempt]);

  // El viewport sólo existe después de la carga: el efecto se vuelve a ejecutar cuando aparece.
  useLayoutEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const resize = () => setViewportSize({ width: element.clientWidth, height: element.clientHeight });
    resize();
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
    observer?.observe(element);
    window.addEventListener('resize', resize);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', resize);
    };
  }, [loaded]);

  // Tamaños reales de las tarjetas en unidades del mundo (no dependen del zoom actual).
  const measureCardSizes = useCallback((): Map<string, CardSize> => {
    const elements = viewportRef.current?.querySelectorAll<HTMLElement>('[data-card-id]') ?? [];
    return new Map(Array.from(elements).flatMap((element) => {
      const id = element.dataset.cardId;
      if (!id) return [];
      const bounds = element.getBoundingClientRect();
      return [[id, { width: bounds.width / zoom, height: bounds.height / zoom }] as const];
    }));
  }, [zoom]);

  const centerCamera = useCallback((board: BoardDocument | null) => {
    const { width, height } = viewportSize;
    if (!width || !height) return;
    const camera = fitBoardCamera(board?.cards ?? [], { width, height }, measureCardSizes());
    setZoom(camera.zoom);
    setPan(camera.pan);
  }, [measureCardSizes, viewportSize]);

  useEffect(() => {
    if (!viewportSize.width || !viewportSize.height) return;
    if (!initializedCamera.current) {
      initializedCamera.current = true;
      centerCamera(null);
    }
  }, [centerCamera, viewportSize]);

  useEffect(() => {
    if (!loaded || !activeBoard || !viewportSize.width || !viewportSize.height) return;
    if (!previousBoardId.current || previousBoardId.current !== activeBoard.id) centerCamera(activeBoard);
    previousBoardId.current = activeBoard.id;
  }, [activeBoard, centerCamera, loaded, viewportSize]);

  useEffect(() => {
    if (!loaded || !activeBoardId) return;
    rememberActiveBoard(activeBoardId);
  }, [activeBoardId, loaded]);

  const updateBoard = useCallback((
    mutate: (board: BoardDocument) => BoardDocument,
    options: { recordHistory?: boolean; coalesceKey?: string } = {},
  ) => {
    if (!activeBoard) return;
    const nextBoard = { ...mutate(activeBoard), updatedAt: new Date().toISOString() };
    if (options.recordHistory !== false) {
      setBoardHistories((current) => ({
        ...current,
        [activeBoard.id]: recordBoardChange(current[activeBoard.id] ?? emptyBoardHistory(), activeBoard, nextBoard, options.coalesceKey),
      }));
    }
    enqueueBoardSave(nextBoard);
    setBoards((current) => current.map((board) => board.id === activeBoard.id ? nextBoard : board));
  }, [activeBoard]);

  /** Una lectura aceptada puede caer en la Biblioteca aunque el tablero abierto sea otro. */
  const updateBoardById = useCallback((
    boardId: string,
    mutate: (board: BoardDocument) => BoardDocument,
    options: { recordHistory?: boolean; coalesceKey?: string } = {},
  ) => {
    const target = boards.find((board) => board.id === boardId);
    if (!target) return;
    const nextBoard = { ...mutate(target), updatedAt: new Date().toISOString() };
    if (options.recordHistory !== false) {
      setBoardHistories((current) => ({
        ...current,
        [boardId]: recordBoardChange(current[boardId] ?? emptyBoardHistory(), target, nextBoard, options.coalesceKey),
      }));
    }
    enqueueBoardSave(nextBoard);
    setBoards((current) => current.map((board) => board.id === boardId ? nextBoard : board));
  }, [boards]);

  const aceptarLecturaEnReferente = useCallback((boardId: string, cardId: string, lectura: Lectura) => {
    const nombre = boards
      .find((board) => board.id === boardId)
      ?.cards.find((card) => card.id === cardId)
      ?.title;
    updateBoardById(boardId, (board) => ({
      ...board,
      cards: board.cards.map((card) => card.id === cardId ? aceptarLectura(card, lectura) : card),
    }));
    setNotice(`Lectura aceptada y guardada en «${nombre || 'el referente'}».`);
  }, [boards, updateBoardById]);

  /** Crea una tarjeta con la herramienta del registro, en el centro de la vista. */
  const addToolCard = useCallback((toolId: string, configure?: (card: BoardCard) => void): BoardCard | null => {
    const tool = getBoardTool(toolId);
    if (!activeBoard) return null;
    if (frameToolId) setNotice(null);
    setFrameToolId(null);
    setFrameDraft(null);
    frameDraw.current = null;
    if (!tool) {
      setNotice(`La herramienta «${toolId}» no está instalada.`);
      return null;
    }
    const center = screenToWorld({ x: viewportSize.width / 2, y: viewportSize.height / 2 }, { pan, zoom });
    const card = tool.crear(center.x - 130, center.y - 90) as BoardCard;
    configure?.(card);
    updateBoard((board) => ({ ...board, cards: [...board.cards, card] }));
    setSelectedCardIds([card.id]);
    return card;
  }, [activeBoard, frameToolId, pan, updateBoard, viewportSize, zoom]);

  const chooseTool = useCallback((toolId: string) => {
    setAddMenuOpen(false);
    const tool = getBoardTool(toolId);
    if (tool?.tipo === 'marco') {
      setFrameToolId(toolId);
      setNotice('Arrastra en la pizarra para dibujar el marco. Escape para cancelar.');
      return;
    }
    setFrameToolId(null);
    addToolCard(toolId);
  }, [addToolCard]);

  /** El marco se dibuja arrastrando; las tarjetas cuyo centro cae dentro pasan a ser hijas por id. */
  const createFrameFromRect = useCallback((rect: FrameRect, toolId: string) => {
    const tool = getBoardTool(toolId);
    if (!tool || !activeBoard) return;
    const frame = tool.crear(rect.x, rect.y) as BoardCard;
    // Entropía pinta copias de las fuentes, no adopta las tarjetas que queden debajo.
    const children = esMarcoEntropia(frame) ? [] : cardsInsideFrame(activeBoard.cards, rect, measureCardSizes());
    const data = readFrameData(frame);
    frame.width = Math.max(FRAME_MIN_SIZE, rect.width);
    frame.datos = {
      ...frame.datos,
      ...data,
      alto: Math.max(FRAME_MIN_SIZE, rect.height),
      hijos: children,
      vista: 'libre',
    };
    updateBoard((board) => ({ ...board, cards: [...board.cards, frame] }));
    setSelectedCardIds([frame.id]);
    setFrameToolId(null);
    setFrameDraft(null);
    setNotice(children.length === 0
      ? 'Marco creado. No quedó ninguna tarjeta dentro.'
      : `Marco creado con ${children.length} ${children.length === 1 ? 'tarjeta' : 'tarjetas'} dentro.`);
  }, [activeBoard, measureCardSizes, updateBoard]);

  const handleWheel = useCallback((event: WheelEvent) => {
    event.preventDefault();
    if (event.metaKey || event.ctrlKey) {
      const rect = viewportRef.current?.getBoundingClientRect();
      if (!rect) return;
      const cursorX = event.clientX - rect.left;
      const cursorY = event.clientY - rect.top;
      const camera = zoomAtPoint({ pan, zoom }, zoom * Math.exp(-event.deltaY * 0.0012), { x: cursorX, y: cursorY });
      setPan(camera.pan);
      setZoom(camera.zoom);
    } else {
      setPan((current) => ({ x: current.x - event.deltaX, y: current.y - event.deltaY }));
    }
  }, [pan, zoom]);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    element.addEventListener('wheel', handleWheel, { passive: false });
    return () => element.removeEventListener('wheel', handleWheel);
  }, [handleWheel, loaded]);

  const zoomBy = (factor: number) => {
    const { width, height } = viewportSize;
    const camera = zoomAtPoint({ pan, zoom }, zoom * factor, { x: width / 2, y: height / 2 });
    setPan(camera.pan);
    setZoom(camera.zoom);
  };

  const fitBoard = () => centerCamera(activeBoard);

  const beginPan = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || (event.target as HTMLElement).closest('.board-card, .board-frame, .board-controls, .board-dialog, button, input, select, a, .board-empty')) return;
    panDrag.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
    setIsPanning(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const movePan = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = panDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    setPan({ x: drag.panX + event.clientX - drag.x, y: drag.panY + event.clientY - drag.y });
  };

  const endPan = (event: React.PointerEvent<HTMLDivElement>) => {
    if (panDrag.current?.pointerId === event.pointerId) {
      panDrag.current = null;
      setIsPanning(false);
    }
  };

  const viewportWorldPoint = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, { pan, zoom });
  };

  const startFrameDraw = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !frameToolId) return;
    if ((event.target as HTMLElement).closest('button, input, select, textarea, a, .board-zoom-controls, .board-empty, .board-controls')) return;
    const start = viewportWorldPoint(event);
    frameDraw.current = { pointerId: event.pointerId, start };
    setFrameDraft(rectFromPoints(start, start));
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveFrameDraw = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = frameDraw.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    setFrameDraft(rectFromPoints(drag.start, viewportWorldPoint(event)));
  };

  const endFrameDraw = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = frameDraw.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const rect = rectFromPoints(drag.start, viewportWorldPoint(event));
    frameDraw.current = null;
    suppressViewportClick.current = true;
    window.setTimeout(() => { suppressViewportClick.current = false; }, 0);
    if (!frameToolId) {
      setFrameDraft(null);
      return;
    }
    if (rect.width < FRAME_MIN_SIZE || rect.height < FRAME_MIN_SIZE) {
      setFrameDraft(null);
      setNotice(`El marco necesita al menos ${FRAME_MIN_SIZE} × ${FRAME_MIN_SIZE}. Vuelve a arrastrar o pulsa Escape.`);
      return;
    }
    createFrameFromRect(rect, frameToolId);
  };

  const beginViewportGesture = (event: React.PointerEvent<HTMLDivElement>) => {
    if (frameToolId) {
      startFrameDraw(event);
      return;
    }
    beginPan(event);
  };

  const moveViewportGesture = (event: React.PointerEvent<HTMLDivElement>) => {
    if (frameDraw.current) moveFrameDraw(event);
    else movePan(event);
  };

  const endViewportGesture = (event: React.PointerEvent<HTMLDivElement>) => {
    if (frameDraw.current) endFrameDraw(event);
    else endPan(event);
  };

  const startCardDrag = (card: BoardCard, event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || frameToolId || connectMode || (event.target as HTMLElement).closest('input,button,a,textarea,select') || !activeBoard) return;
    suppressCardClick.current = false;
    const hasModifier = event.shiftKey || event.metaKey || event.ctrlKey;
    let nextSelection = selectedCardIds;
    if (event.metaKey || event.ctrlKey) {
      nextSelection = selectedCardIds.includes(card.id)
        ? selectedCardIds.filter((id) => id !== card.id)
        : [...selectedCardIds, card.id];
      suppressCardClick.current = true;
    } else if (event.shiftKey && !selectedCardIds.includes(card.id)) {
      nextSelection = [...selectedCardIds, card.id];
      suppressCardClick.current = true;
    } else if (!hasModifier && !selectedCardIds.includes(card.id)) {
      nextSelection = [card.id];
    }
    if (nextSelection !== selectedCardIds) setSelectedCardIds(nextSelection);
    if (hasModifier && !nextSelection.includes(card.id)) return;

    const ids = hasModifier
      ? [card.id]
      : card.type === 'marco'
        ? [...new Set([...nextSelection.includes(card.id) ? nextSelection : [card.id], ...readFrameData(card).hijos])]
        : nextSelection.includes(card.id) ? nextSelection : [card.id];
    const positions = new Map(
      activeBoard.cards.filter((item) => ids.includes(item.id)).map((item) => [item.id, { x: item.x, y: item.y }]),
    );
    cardDrag.current = {
      pointerId: event.pointerId,
      boardId: activeBoard.id,
      ids,
      x: event.clientX,
      y: event.clientY,
      positions,
      startBoard: activeBoard,
      gesture: newBoardId('move'),
      moved: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveCardDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = cardDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    let deltaX = (event.clientX - drag.x) / zoom;
    let deltaY = (event.clientY - drag.y) / zoom;
    const anchor = drag.positions.get(drag.ids[0]);
    if (snapEnabled && anchor) {
      deltaX = snapPosition(anchor.x + deltaX, GRID_SIZE) - anchor.x;
      deltaY = snapPosition(anchor.y + deltaY, GRID_SIZE) - anchor.y;
    }
    if (deltaX !== 0 || deltaY !== 0) drag.moved = true;
    updateBoard((board) => ({
      ...board,
      cards: board.cards.map((item) => {
        const position = drag.positions.get(item.id);
        return position ? { ...item, x: position.x + deltaX, y: position.y + deltaY } : item;
      }),
    }), { recordHistory: false });
  };

  const endCardDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = cardDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (activeBoard?.id === drag.boardId && drag.ids.some((id) => {
      const before = drag.startBoard.cards.find((item) => item.id === id);
      const after = activeBoard.cards.find((item) => item.id === id);
      return before && after && (before.x !== after.x || before.y !== after.y);
    })) {
      setBoardHistories((current) => ({
        ...current,
        [drag.boardId]: recordBoardChange(current[drag.boardId] ?? emptyBoardHistory(), drag.startBoard, activeBoard, drag.gesture),
      }));
    }
    if (drag.moved) suppressCardClick.current = true;
    cardDrag.current = null;
  };

  const alignSelection = (alignment: Alignment) => {
    if (selectedCardIds.length < 2) return;
    const sizes = measureCardSizes();
    updateBoard((board) => ({
      ...board,
      cards: alignCards(board.cards, selectedCardIds, alignment, sizes),
    }));
  };

  const distributeSelection = (axis: DistributionAxis) => {
    if (selectedCardIds.length < 3) return;
    const sizes = measureCardSizes();
    updateBoard((board) => ({
      ...board,
      cards: distributeCards(board.cards, selectedCardIds, axis, sizes),
    }));
  };

  const undo = useCallback(() => {
    if (!activeBoard) return;
    const history = boardHistories[activeBoard.id] ?? emptyBoardHistory();
    const result = undoBoardChange(history, activeBoard);
    if (!result.board) return;
    setBoardHistories((current) => ({ ...current, [activeBoard.id]: result.history }));
    setBoards((current) => current.map((board) => board.id === activeBoard.id ? result.board! : board));
    setSelectedCardIds((current) => current.filter((id) => result.board!.cards.some((card) => card.id === id)));
    enqueueBoardSave(result.board!);
  }, [activeBoard, boardHistories]);

  const redo = useCallback(() => {
    if (!activeBoard) return;
    const history = boardHistories[activeBoard.id] ?? emptyBoardHistory();
    const result = redoBoardChange(history, activeBoard);
    if (!result.board) return;
    setBoardHistories((current) => ({ ...current, [activeBoard.id]: result.history }));
    setBoards((current) => current.map((board) => board.id === activeBoard.id ? result.board! : board));
    setSelectedCardIds((current) => current.filter((id) => result.board!.cards.some((card) => card.id === id)));
    enqueueBoardSave(result.board!);
  }, [activeBoard, boardHistories]);

  useEffect(() => {
    const handleHistoryShortcut = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLocaleLowerCase() !== 'z') return;
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('input, textarea, [contenteditable="true"]')) return;
      event.preventDefault();
      if (event.shiftKey) redo();
      else undo();
    };
    window.addEventListener('keydown', handleHistoryShortcut);
    return () => window.removeEventListener('keydown', handleHistoryShortcut);
  }, [redo, undo]);

  useEffect(() => {
    const handleAddShortcut = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target;
      const typing = target instanceof HTMLElement && Boolean(target.closest('input, textarea, select, [contenteditable="true"]'));
      if (event.key === 'Escape') {
        if (archiveFullscreenId) {
          event.preventDefault();
          setArchiveFullscreenId(null);
          return;
        }
        if (frameToolId) {
          event.preventDefault();
          frameDraw.current = null;
          setFrameDraft(null);
          setFrameToolId(null);
          setNotice(null);
          return;
        }
        if (addMenuOpen) {
          event.preventDefault();
          setAddMenuOpen(false);
        }
        return;
      }
      if (archiveFullscreenId) return;
      if (typing || event.key.toLocaleLowerCase() !== 'n') return;
      event.preventDefault();
      setAddMenuOpen((open) => !open);
    };
    window.addEventListener('keydown', handleAddShortcut);
    return () => window.removeEventListener('keydown', handleAddShortcut);
  }, [addMenuOpen, archiveFullscreenId, frameToolId]);

  const handleCardSelection = (cardId: string, event: React.MouseEvent<HTMLElement>) => {
    if (suppressCardClick.current) {
      suppressCardClick.current = false;
      return;
    }
    if (event.metaKey || event.ctrlKey) {
      setSelectedCardIds((current) => current.includes(cardId) ? current.filter((id) => id !== cardId) : [...current, cardId]);
    } else if (event.shiftKey) {
      setSelectedCardIds((current) => current.includes(cardId) ? current : [...current, cardId]);
    } else {
      setSelectedCardIds([cardId]);
    }
  };

  const handleConnectCard = (cardId: string) => {
    if (!connectMode || !activeBoard) return;
    if (!connectFromId) {
      setConnectFromId(cardId);
      setNotice('Ahora elige otra tarjeta para crear la relación.');
      return;
    }
    if (connectFromId === cardId) {
      setConnectFromId(null);
      setNotice('Relación cancelada.');
      return;
    }
    const exists = activeBoard.relations.some((relation) => [relation.from, relation.to].sort().join(':') === [connectFromId, cardId].sort().join(':'));
    if (exists) setNotice('Estas tarjetas ya están relacionadas.');
    else {
      updateBoard((board) => ({ ...board, relations: [...board.relations, { id: newBoardId('relation'), from: connectFromId, to: cardId }] }));
      setNotice('Relación creada.');
    }
    setConnectFromId(null);
  };

  const createBoardInProject = async (projectId: string, title = 'Nuevo tablero') => {
    const board = createBoard(title);
    await assignBoardToProject(board.id, projectId);
    setProjectIdByBoardId((current) => new Map(current).set(board.id, projectId));
    setBoards((current) => [...current, board]);
    setActiveBoardId(board.id);
    setSelectedCardIds([]);
    enqueueBoardSave(board, { immediate: true });
  };

  const handleProjectSelect = async (projectId: string) => {
    if (!projects.some((project) => project.id === projectId)) return;
    if (!(await flushBoardWrites())) {
      setNotice('No se cambió de proyecto porque el tablero actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    try {
      await setActiveProject(projectId);
      setActiveProjectId(projectId);
      setProjectError(null);
      const nextBoard = boards.find((board) => projectIdByBoardId.get(board.id) === projectId);
      if (nextBoard) setActiveBoardId(nextBoard.id);
      else await createBoardInProject(projectId, 'Mi tablero');
      setSelectedCardIds([]);
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo cambiar de proyecto.');
    }
  };

  const handleCreateProject = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = projectName.trim().slice(0, 120);
    if (!name) return;
    if (!(await flushBoardWrites())) {
      setNotice('No se creó el proyecto porque el tablero actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    try {
      const project = await createProject(name);
      setProjects((current) => [...current, project]);
      const board = createBoard('Mi tablero');
      await assignBoardToProject(board.id, project.id);
      await setActiveProject(project.id);
      setProjectIdByBoardId((current) => new Map(current).set(board.id, project.id));
      setBoards((current) => [...current, board]);
      setActiveProjectId(project.id);
      setActiveBoardId(board.id);
      setSelectedCardIds([]);
      enqueueBoardSave(board, { immediate: true });
      setProjectError(null);
      setProjectName('');
      setProjectDialog(false);
      setNotice('Proyecto creado. Tus tableros siguen guardándose localmente.');
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo crear el proyecto.');
    }
  };

  const handleSavePdfReference = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!activeProject || !activeBoard || !pdfReferenceSource) return;
    const reference = createPdfReference({
      projectId: activeProject.id,
      boardId: activeBoard.id,
      source: pdfReferenceSource,
      quote: pdfReferenceQuote,
      note: pdfReferenceNote,
    });
    if (!reference) {
      setNotice('No se pudo validar la referencia. Comprueba que el PDF y la página estén disponibles.');
      return;
    }
    try {
      await savePdfReference(reference);
      setProjectReferences((current) => [reference, ...current]);
      setPdfReferenceQuote('');
      setPdfReferenceNote('');
      setPdfReferenceDialog(false);
      setReferencesOpen(true);
      setNotice('Referencia guardada en el proyecto. No se copió el PDF.');
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo guardar la referencia PDF.');
    }
  };

  const handleOpenPdfReference = (reference: PdfReference) => {
    if (!onOpenPdfReference?.(reference)) {
      setNotice('Abre el mismo PDF en PROMETEO para saltar a esta página. La referencia conserva su huella SHA-256.');
      return;
    }
    setReferencesOpen(false);
    setNotice('PDF abierto en la página ' + reference.page + '.');
  };

  const handleDeletePdfReference = async (reference: PdfReference) => {
    if (!window.confirm('¿Eliminar la referencia a «' + reference.sourceName + '», página ' + reference.page + '?')) return;
    try {
      await deletePdfReference(reference.id);
      setProjectReferences((current) => current.filter((item) => item.id !== reference.id));
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo eliminar la referencia PDF.');
    }
  };

  const exportProjectMarkdown = () => {
    if (!activeProject) return;
    downloadText(
      boardFilename(activeProject.name, 'md'),
      projectToMarkdown(activeProject, projectBoards, activeProjectReferences),
      'text/markdown;charset=utf-8',
    );
    setNotice('Markdown del proyecto listo para Obsidian. Los PDF permanecen en su ubicación original.');
  };

  const addNewBoard = async () => {
    if (!(await flushBoardWrites())) {
      setNotice('No se creó otro tablero porque el actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    if (activeProjectId) {
      try {
        await createBoardInProject(activeProjectId);
        return;
      } catch (error) {
        setProjectError(error instanceof Error ? error.message : 'No se pudo asignar el tablero al proyecto.');
        return;
      }
    }
    const board = createBoard('Nuevo tablero');
    setBoards((current) => [...current, board]);
    setActiveBoardId(board.id);
    setSelectedCardIds([]);
    enqueueBoardSave(board, { immediate: true });
  };

  const renameBoard = (title: string) => {
    updateBoard((board) => ({ ...board, title: title.slice(0, 120) }));
  };

  const removeCurrentBoard = async () => {
    if (!activeBoard || !window.confirm(`¿Eliminar «${activeBoard.title}» y sus tarjetas?`)) return;
    if (!(await flushBoardWrites())) {
      setNotice('No se eliminó el tablero porque tiene cambios sin guardar. Reintenta o exporta una copia.');
      return;
    }
    try {
      await removeBoardFromStore(activeBoard.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo quitar el tablero guardado.');
      return;
    }
    try { await removeBoardProjectLink(activeBoard.id); } catch { /* El vínculo huérfano no borra referencias ni otros tableros. */ }
    const remaining = boards.filter((board) => board.id !== activeBoard.id);
    setProjectIdByBoardId((current) => {
      const next = new Map(current);
      next.delete(activeBoard.id);
      return next;
    });
    setSelectedCardIds([]);
    setConnectFromId(null);
    setBoards(remaining);
    const nextInProject = remaining.find((board) => !activeProjectId || projectIdByBoardId.get(board.id) === activeProjectId);
    if (nextInProject) {
      setActiveBoardId(nextInProject.id);
    } else {
      try {
        if (activeProjectId) await createBoardInProject(activeProjectId, 'Mi tablero');
        else {
          const fresh = createBoard('Mi tablero');
          setBoards([fresh]);
          setActiveBoardId(fresh.id);
          enqueueBoardSave(fresh, { immediate: true });
        }
      } catch (error) {
        setNotice(error instanceof Error ? error.message : 'No se pudo crear un tablero de reemplazo.');
      }
    }
  };

  const saveLinkCard = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isSafeExternalUrl(linkUrl)) {
      setLinkError('Usa una dirección web completa que empiece con http:// o https://.');
      return;
    }
    if (!activeBoard) return;
    const created = addToolCard('link', (card) => {
      card.title = linkTitle.trim() || linkUrl.trim();
      card.url = linkUrl.trim();
    });
    if (!created) return;
    setLinkDialog(false);
    setLinkTitle('');
    setLinkUrl('');
    setLinkError(null);
  };

  const addMedia = async (file?: File) => {
    if (!file || !activeBoard) return;
    if (file.size > MAX_MEDIA_BYTES) {
      setNotice('Este prototipo guarda archivos de hasta 12 MB. Reduce el tamaño y vuelve a intentarlo.');
      return;
    }
    try {
      const mimeType = file.type || 'application/octet-stream';
      const dataUrl = await readFileAsDataUrl(file);
      const kind = mimeType.startsWith('image/') ? 'image' : mimeType.startsWith('video/') ? 'video' : mimeType.startsWith('audio/') ? 'audio' : 'file';
      const media: BoardMedia = { name: file.name, mimeType, dataUrl, kind };
      const created = addToolCard('media', (card) => {
        card.title = media.name.replace(/\.[^.]+$/, '') || 'Recurso';
        card.media = media;
      });
      if (!created) return;
      setNotice('Recurso añadido y guardado dentro del tablero local.');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo añadir el archivo.');
    }
  };

  const importBoard = async (file?: File) => {
    if (!file) return;
    try {
      if (!(await flushBoardWrites())) throw new Error('El tablero actual no se guardó; el archivo no se importó. Reintenta o exporta una copia.');
      const contents = await file.text();
      const imported = file.name.toLocaleLowerCase().endsWith('.md') ? markdownToBoard(contents) : parseBoardImport(JSON.parse(contents));
      if (!imported) throw new Error('El archivo no tiene un tablero de Prometeo válido.');
      const copy = cloneBoardForImport(imported);
      if (activeProjectId) await assignBoardToProject(copy.id, activeProjectId);
      setBoards((current) => [...current, copy]);
      if (activeProjectId) setProjectIdByBoardId((current) => new Map(current).set(copy.id, activeProjectId));
      setActiveBoardId(copy.id);
      setSelectedCardIds([]);
      enqueueBoardSave(copy, { immediate: true });
      setNotice(file.name.toLocaleLowerCase().endsWith('.md') ? 'Markdown importado como un tablero nuevo.' : 'Copia del tablero importada.');
      setLoadError(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo importar el archivo.');
    }
  };

  /** Crea o actualiza «Biblioteca» con la semilla de referentes, sin duplicar tarjetas. */
  const importReferentes = async () => {
    if (!(await flushBoardWrites())) {
      setNotice('No se importaron los referentes porque el tablero actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    const result = importarBiblioteca(boards, undefined, {
      projectId: activeProjectId || undefined,
      projectIdByBoardId,
    });
    if (result.created && activeProjectId) {
      try {
        await assignBoardToProject(result.board.id, activeProjectId);
      } catch (error) {
        setProjectError(error instanceof Error ? error.message : 'No se pudo asignar la Biblioteca al proyecto.');
        return;
      }
      setProjectIdByBoardId((current) => new Map(current).set(result.board.id, activeProjectId));
    }
    setBoards((current) => current.some((board) => board.id === result.board.id)
      ? current.map((board) => board.id === result.board.id ? result.board : board)
      : [...current, result.board]);
    setActiveBoardId(result.board.id);
    setSelectedCardIds([]);
    enqueueBoardSave(result.board, { immediate: true });
    setNotice(result.created
      ? `Tablero «Biblioteca» creado con ${result.referentes} referentes en ${result.marcos} marcos.`
      : `Tablero «Biblioteca» actualizado: ${result.referentes} referentes en ${result.marcos} marcos, sin duplicados.`);
  };

  /** Suma los ♥/✕ de un `gustos-parcial.json` a la memoria del proyecto activo. */
  const importGustos = async (file?: File) => {
    if (!file) return;
    if (!activeProject) {
      setNotice('Entropía necesita un proyecto activo para recordar el gusto.');
      return;
    }
    if (file.size > 2_000_000) {
      setNotice('El archivo de gustos es demasiado grande (máximo 2 MB).');
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      setNotice('El archivo de gustos no es un JSON válido.');
      return;
    }
    const resultado = importarGustosParciales(activeProject.gustos, parsed);
    if (!resultado.likes && !resultado.nopes) {
      setNotice('El archivo no tiene votos de Entropía válidos.');
      return;
    }
    actualizarGustosProyecto(() => resultado.gustos);
    setNotice(`Gustos importados: ${resultado.likes} ♥ y ${resultado.nopes} ✕${resultado.ignorados ? `; ${resultado.ignorados} ignorados` : ''}.`);
  };

  const exportJson = () => {
    if (!activeBoard) return;
    downloadText(boardFilename(activeBoard.title, 'json'), JSON.stringify(makeBoardExport(activeBoard), null, 2), 'application/json');
    setNotice('El tablero y sus adjuntos se exportaron en JSON.');
  };

  const exportMarkdown = () => {
    if (!activeBoard) return;
    const markdown = boardToMarkdown(activeBoard, {
      cardMarkdown: (card) => {
        const tool = getBoardTool(card.type);
        return tool?.exportarMarkdown ? tool.exportarMarkdown(card) : null;
      },
    });
    downloadText(boardFilename(activeBoard.title, 'md'), markdown, 'text/markdown;charset=utf-8');
    setNotice('Markdown listo para Obsidian. Los adjuntos multimedia permanecen en la exportación JSON.');
  };

  /** Un .md por referente con frontmatter y enlaces [[ ]] a los del mismo marco. */
  const exportReferentesObsidian = () => {
    const notas = notasObsidian(projectBoards);
    if (!notas.length) {
      setNotice('No hay referentes que exportar. Importa la biblioteca primero.');
      return;
    }
    const bytes = construirZipObsidian(projectBoards);
    const url = URL.createObjectURL(new Blob([bytes.buffer as ArrayBuffer], { type: 'application/zip' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = activeProject ? `${boardFilename(activeProject.name, 'md').replace(/\.md$/, '')}-referentes.zip` : 'referentes-obsidian.zip';
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
    setNotice(`Obsidian: ${notas.length} ${notas.length === 1 ? 'nota' : 'notas'} de referente en un ZIP.`);
  };

  const updateCard = (id: string, patch: Partial<BoardCard>) => {
    const field = Object.keys(patch)[0];
    const coalesceKey = field === 'title' || field === 'body' ? `card:${id}:${field}:${textSession.current}` : undefined;
    updateBoard((board) => ({ ...board, cards: board.cards.map((card) => card.id === id ? { ...card, ...patch } : card) }), { coalesceKey });
  };

  /** «Ver como» del marco: cambiar de vista no mueve ni borra ninguna tarjeta. */
  const updateFrameView = (id: string, vista: FrameView) => {
    updateBoard((board) => ({ ...board, cards: setFrameView(board.cards, id, vista) }));
  };

  /**
   * Publica la vista actual del marco como carpeta estática local.
   * La carpeta la elige la persona; no se envía nada por la red.
   */
  const publishFrame = async (card: BoardCard) => {
    const data = readFrameData(card);
    if (data.vista === 'libre') {
      setNotice('Elige Archivo, Muro o Mesa de luz antes de publicar.');
      return;
    }
    if (!activeBoard || publishingFrameId) return;
    setPublishingFrameId(card.id);
    setNotice('Eligiendo carpeta y preparando la publicación local…');
    try {
      const result = await publishFrameToDirectory(card.title || 'Archivo', data.vista, activeBoard.cards, data.hijos);
      setNotice(result.cancelled
        ? 'Publicación cancelada.'
        : result.zip
          ? `ZIP descargado: ${result.files} archivos (${result.media} ${result.media === 1 ? 'pieza' : 'piezas'}). Descomprímelo y abre index.html sin servidor.`
          : `Publicado en «${result.folder}»: ${result.files} archivos (${result.media} ${result.media === 1 ? 'pieza' : 'piezas'}). Abre index.html sin servidor.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo publicar el marco.');
    } finally {
      setPublishingFrameId(null);
    }
  };

  /**
   * Crea un marco nuevo en vista Archivo con el manifiesto como nota fija y
   * los collages de la semana convertidos en piezas del feed.
   */
  const crearManifiesto = async () => {
    if (!activeBoard || manifesting) return;
    const sourceBoards = projectBoards.length ? projectBoards : [activeBoard];
    const ahora = new Date();
    const seleccion = seleccionarSemana(sourceBoards, {
      ahora,
      gustos: activeProject?.gustos ?? gustosVacios(),
    });
    if (!seleccion.collages.length && !seleccion.lecturas.length && !seleccion.pesos.length) {
      setNotice('No hay nada que contar esta semana: faltan collages con ♥, lecturas aceptadas o pesos que hayan subido.');
      return;
    }
    setManifesting(true);
    try {
      const resultado = await pedirManifiesto(seleccion, activeProject?.name || activeBoard.title || 'el proyecto abierto');
      const maxX = activeBoard.cards.length
        ? Math.max(...activeBoard.cards.map((card) => card.x + card.width))
        : 0;
      const minY = activeBoard.cards.length
        ? Math.min(...activeBoard.cards.map((card) => card.y))
        : 0;
      const { frame, cards } = crearMarcoManifiesto(seleccion, resultado.lineas, {
        x: maxX + 80,
        y: minY,
        fuentes: fuentesEntropia,
        ahora,
      });
      updateBoard((board) => ({ ...board, cards: [...board.cards, ...cards] }));
      setSelectedCardIds([frame.id]);
      setNotice(resultado.disponible
        ? `Manifiesto creado con ${seleccion.collages.length} ${seleccion.collages.length === 1 ? 'collage' : 'collages'} y ${resultado.lineas.length} líneas. Abre «Ver como Archivo» o pulsa «Publicar».`
        : `Sin DeepSeek (${resultado.motivo}). El marco ya está creado con 12 líneas vacías para escribir a mano.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo crear el manifiesto.');
    } finally {
      setManifesting(false);
    }
  };

  /** Las herramientas entregan la tarjeta completa; se conserva el agrupado de deshacer por campo de texto. */
  const replaceCard = useCallback((next: BoardCard) => {
    const current = activeBoard?.cards.find((card) => card.id === next.id);
    if (!current) return;
    const changed = (Object.keys(next) as Array<keyof BoardCard>).filter((key) => next[key] !== current[key]);
    const field = changed.length === 1 ? changed[0] : null;
    const coalesceKey = field === 'title' || field === 'body' ? `card:${next.id}:${field}:${textSession.current}` : undefined;
    updateBoard((board) => ({ ...board, cards: board.cards.map((card) => card.id === next.id ? next : card) }), { coalesceKey });
  }, [activeBoard, updateBoard]);

  /** La memoria de gusto vive en el proyecto y se escribe en su propio almacén. */
  const actualizarGustosProyecto = useCallback((actualizar: (gustos: Gustos) => Gustos) => {
    if (!activeProject) {
      setNotice('Entropía necesita un proyecto activo para recordar el gusto.');
      return;
    }
    const siguiente = actualizar(activeProject.gustos);
    setProjects((current) => current.map((project) =>
      project.id === activeProject.id
        ? { ...project, gustos: siguiente, updatedAt: new Date().toISOString() }
        : project,
    ));
    void saveProjectGustos(activeProject.id, siguiente).catch((error: unknown) => {
      setNotice(error instanceof Error ? error.message : 'No se pudo guardar la memoria de gusto.');
    });
  }, [activeProject]);

  /** Tira con una semilla (nueva o la indicada) y deja la tirada dentro del marco. */
  const tirarEnMarcoEntropia = (card: BoardCard, semilla: string = nuevaSemilla()) => {
    const frame = readFrameData(card);
    const tamano = { ancho: Math.max(120, card.width), alto: Math.max(120, frame.alto - 96) };
    try {
      const tirada = tirarEntropia({
        semilla,
        fuentes: fuentesEntropia,
        herramientas: listBoardTools().map((tool) => ({ id: tool.id, nombre: tool.nombre })),
        tamano,
        gustos: activeProject?.gustos ?? gustosVacios(),
      });
      updateCard(card.id, { datos: { ...card.datos, ...tirada } });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo tirar la combinación.');
    }
  };

  const combinacionDeTirada = (datos: EntropiaDatos) => ({
    semilla: datos.semilla,
    referentes: datos.fuentes,
    herramienta: datos.herramienta,
    regla: datos.regla,
    restriccion: datos.restriccion,
    azarPuro: datos.azarPuro,
  });

  /** ♥ guarda una copia con procedencia y suma 1 a los gustos del proyecto. */
  const guardarCollageEntropia = (card: BoardCard) => {
    const datos = leerEntropia(card);
    if (!datos) return;
    const guardado: EntropiaDatos = { ...datos, guardado: true, creado: new Date().toISOString() };
    const nueva: BoardCard = {
      ...card,
      id: newBoardId('card'),
      x: card.x + card.width + 32,
      y: card.y,
      title: `Collage · ${datos.reglaNombre || datos.regla}`,
      datos: { ...card.datos, ...guardado, hijos: [], vista: 'libre' },
    };
    updateBoard((board) => ({ ...board, cards: [...board.cards, nueva] }));
    setSelectedCardIds([nueva.id]);
    actualizarGustosProyecto((gustos) => like(gustos, combinacionDeTirada(datos)));
    setNotice(`Collage guardado con la semilla ${datos.semilla}.`);
  };

  /** ✕ solo resta 1 a los gustos; la tirada se queda como estaba. */
  const descartarCollageEntropia = (card: BoardCard) => {
    const datos = leerEntropia(card);
    if (!datos) return;
    actualizarGustosProyecto((gustos) => nope(gustos, combinacionDeTirada(datos)));
    setNotice('Entropía: «no» recordado sin tocar el collage.');
  };

  /**
   * Pegar una URL de imagen sobre un Referente (o con uno seleccionado) añade un
   * medio que apunta a esa fuente con la fecha del día. No descarga la imagen.
   */
  useEffect(() => {
    const handlePaste = (event: ClipboardEvent) => {
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('input, textarea, select, [contenteditable="true"]')) return;
      const text = event.clipboardData?.getData('text/plain').trim() ?? '';
      if (!text || !isSafeExternalUrl(text)) return;
      const selectedId = selectedCardIds.length === 1 ? selectedCardIds[0] : null;
      const targetId = hoveredReferenteId.current ?? selectedId;
      if (!targetId) return;
      const card = activeBoard?.cards.find((item) => item.id === targetId && item.type === 'referente');
      if (!card) return;
      const before = leerReferente(card);
      const next = agregarImagenDesdeUrl(before, text);
      if (!next) return;
      event.preventDefault();
      if (next.imagenes.length === before.imagenes.length) {
        setNotice('Esa imagen ya estaba en el Referente, con su fuente y fecha.');
        return;
      }
      replaceCard({ ...card, title: next.nombre.trim() || card.title, datos: { ...card.datos, ...next } });
      setNotice(`Imagen añadida a «${next.nombre || card.title || 'Referente'}» con su fuente y fecha.`);
    };
    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, [activeBoard, replaceCard, selectedCardIds]);

  const removeCard = (id: string) => {
    const card = activeBoard?.cards.find((item) => item.id === id);
    const isFrame = card?.type === 'marco';
    if (!window.confirm(isFrame
      ? '¿Eliminar este marco? Las tarjetas de dentro seguirán en la pizarra.'
      : '¿Eliminar esta tarjeta y sus relaciones?')) return;
    updateBoard((board) => {
      const cards = isFrame
        ? removeFrameKeepingChildren(board.cards, id)
        : detachCardFromFrames(board.cards.filter((item) => item.id !== id), id);
      return {
        ...board,
        cards,
        relations: board.relations.filter((relation) => relation.from !== id && relation.to !== id),
      };
    });
    setSelectedCardIds((current) => current.filter((selectedId) => selectedId !== id));
  };

  const deleteSelectedCards = () => {
    if (!selectedCardIds.length || !activeBoard) return;
    const count = selectedCardIds.length;
    if (!window.confirm(`¿Eliminar ${count} ${count === 1 ? 'tarjeta seleccionada' : 'tarjetas seleccionadas'} y sus relaciones?`)) return;
    const selected = new Set(selectedCardIds);
    updateBoard((board) => {
      let cards = board.cards.filter((card) => !selected.has(card.id));
      for (const id of selected) cards = detachCardFromFrames(cards, id);
      return {
        ...board,
        cards,
        relations: board.relations.filter((relation) => !selected.has(relation.from) && !selected.has(relation.to)),
      };
    });
    setSelectedCardIds([]);
  };

  const matchingCards = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return new Set((activeBoard?.cards ?? []).filter((card) => !query || `${card.title} ${card.body} ${card.url ?? ''}`.toLocaleLowerCase().includes(query)).map((card) => card.id));
  }, [activeBoard?.cards, search]);

  if (!loaded) {
    return <div className="board-loading" role="status">Abriendo tu tablero…</div>;
  }
  if (!activeBoard) {
    return (
      <div className="board-loading board-no-project-board">
        <div role="status">{projectError ?? 'Este proyecto todavía no tiene un tablero.'}</div>
        <button className="board-tool primary" onClick={() => void addNewBoard()}><Plus size={15} /> Crear tablero</button>
        <button className="board-tool" onClick={onBack}>Volver a PDF Studio</button>
      </div>
    );
  }

  return (
    <div className="board-workspace" inert={locked || undefined}>
      <header className="board-header" data-testid="board-topbar">
        <button className="board-back" onClick={() => void leaveBoard()} title="Volver al espacio PDF">
          <ArrowLeft size={16} aria-hidden="true" /> <span>PDF Studio</span>
        </button>
        <div className="board-heading">
          <span className="board-mark" aria-hidden="true">P</span>
          <label className="sr-only" htmlFor="board-name">Nombre del tablero</label>
          <input id="board-name" value={activeBoard.title} maxLength={120} onChange={(event) => renameBoard(event.target.value)} aria-label="Nombre del tablero" />
          <span className={`board-save-state ${saveState}`} aria-live="polite">
            {saveState === 'saving' ? 'Guardando…' : saveState === 'error' ? 'Sin guardar' : 'Guardado'}
          </span>
        </div>
        <div className="board-header-actions">
          <label className="sr-only" htmlFor="project-select">Proyecto</label>
          <select id="project-select" value={activeProjectId} onChange={(event) => { void handleProjectSelect(event.target.value); }} aria-label="Elegir proyecto" disabled={!projects.length}>
            {projects.length ? projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>) : <option value="">Proyectos no disponibles</option>}
          </select>
          <button className="board-icon-button" onClick={() => { setProjectName(''); setProjectDialog(true); }} aria-label="Crear proyecto" title="Crear proyecto"><FolderPlus size={16} /></button>
          <label className="sr-only" htmlFor="board-select">Tablero</label>
          <select id="board-select" value={activeBoard.id} onChange={async (event) => {
            const saved = await flushBoardWrites();
            if (!saved) {
              setNotice('No se cambió de tablero porque el actual aún no se pudo guardar. Reintenta o exporta una copia.');
              return;
            }
            setActiveBoardId(event.target.value);
            setSelectedCardIds([]);
          }} aria-label="Elegir tablero">
            {projectBoards.map((board) => <option key={board.id} value={board.id}>{board.title || 'Sin título'}</option>)}
          </select>
          <button className="board-icon-button" onClick={addNewBoard} aria-label="Crear tablero" title="Crear tablero"><Plus size={16} /></button>
          <button className="board-icon-button danger" onClick={() => void removeCurrentBoard()} aria-label="Eliminar tablero" title="Eliminar tablero"><Trash2 size={15} /></button>
        </div>
      </header>

      <nav className="board-controls" aria-label="Herramientas del tablero">
        <button className="board-tool" onClick={() => setPdfReferenceDialog(true)} disabled={!activeProject || !pdfReferenceSource} title={pdfReferenceSource ? 'Guardar la página PDF actual como referencia' : 'Abre un PDF para guardar referencias de página'}><BookOpen size={15} /> Referenciar página PDF</button>
        <button className={`board-tool ${referencesOpen ? 'active' : ''}`} onClick={() => setReferencesOpen((open) => !open)} disabled={!activeProjectReferences.length} aria-pressed={referencesOpen} title="Mostrar referencias PDF de este proyecto">Referencias PDF ({activeProjectReferences.length})</button>
        <button className="board-tool" onClick={exportProjectMarkdown} disabled={!activeProject} title="Exportar notas del proyecto para Obsidian">Exportar proyecto a Obsidian</button>
        <span className="board-tool-divider" />
        <div className="board-add">
          <button
            className="board-tool primary"
            onClick={() => setAddMenuOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={addMenuOpen}
            title="Añadir tarjeta (N)"
          >
            <Plus size={15} /> Añadir
          </button>
        </div>
        <button className="board-tool" onClick={() => addToolCard('note')}><StickyNote size={15} /> Nueva nota</button>
        <button className="board-tool" onClick={() => { setLinkDialog(true); setLinkError(null); }}><Link2 size={15} /> Añadir enlace</button>
        <button className="board-tool" onClick={() => mediaInput.current?.click()}><ImagePlus size={15} /> Añadir multimedia</button>
        <span className="board-tool-divider" />
        <button className="board-tool" onClick={undo} disabled={!canUndo} title="Deshacer (⌘/Ctrl + Z)" aria-label="Deshacer">
          <Undo2 size={14} /> Deshacer
        </button>
        <button className="board-tool" onClick={redo} disabled={!canRedo} title="Rehacer (⌘/Ctrl + Shift + Z)" aria-label="Rehacer">
          <Redo2 size={14} /> Rehacer
        </button>
        <button className={`board-tool ${snapEnabled ? 'active' : ''}`} onClick={() => setSnapEnabled((enabled) => !enabled)} aria-pressed={snapEnabled} title="Ajustar movimiento a la cuadrícula">
          <Magnet size={14} /> Ajuste
        </button>
        <button className={`board-tool ${connectMode ? 'active' : ''}`} onClick={() => { setConnectMode((value) => !value); setConnectFromId(null); setNotice(connectMode ? null : 'Elige una tarjeta y luego otra para conectarlas.'); }} aria-pressed={connectMode}>
          <Link2 size={15} /> {connectMode ? 'Terminar relaciones' : 'Relacionar'}
        </button>
        <span className="board-tool-divider" />
        <button className="board-tool" onClick={() => alignSelection('left')} disabled={selectedCardIds.length < 2} title="Alinear a la izquierda">← Alinear</button>
        <button className="board-tool" onClick={() => alignSelection('center-x')} disabled={selectedCardIds.length < 2} title="Alinear los centros sobre el eje vertical">↕ Centro vertical</button>
        <button className="board-tool" onClick={() => alignSelection('right')} disabled={selectedCardIds.length < 2} title="Alinear a la derecha">Alinear →</button>
        <button className="board-tool" onClick={() => alignSelection('top')} disabled={selectedCardIds.length < 2} title="Alinear arriba">↑ Arriba</button>
        <button className="board-tool" onClick={() => alignSelection('center-y')} disabled={selectedCardIds.length < 2} title="Alinear los centros sobre el eje horizontal">↔ Centro horizontal</button>
        <button className="board-tool" onClick={() => alignSelection('bottom')} disabled={selectedCardIds.length < 2} title="Alinear abajo">Abajo ↓</button>
        <button className="board-tool" onClick={() => distributeSelection('horizontal')} disabled={selectedCardIds.length < 3} title="Distribuir con espacios iguales">Distribuir ↔</button>
        <button className="board-tool" onClick={() => distributeSelection('vertical')} disabled={selectedCardIds.length < 3} title="Distribuir verticalmente">Distribuir ↕</button>
        <button className="board-tool danger" onClick={deleteSelectedCards} disabled={!selectedCardIds.length} title="Eliminar tarjetas seleccionadas">Eliminar selección</button>
        <span className="board-tool-divider" />
        <div className="board-search">
          <Search size={14} aria-hidden="true" />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar tarjetas" aria-label="Buscar tarjetas" />
          {search && <button onClick={() => setSearch('')} aria-label="Limpiar búsqueda"><X size={13} /></button>}
        </div>
        <div className="board-spacer" />
        <button className="board-tool" onClick={() => setMirarOpen(true)} title="Elegir tres referentes y unos ojos, y pedir tres lecturas"><Eye size={14} /> Volver a mirar</button>
        <button className="board-tool" onClick={() => void crearManifiesto()} disabled={manifesting} title="Crear un marco con el manifiesto de la semana: collages con ♥, lecturas aceptadas y pesos que subieron">{manifesting ? 'Escribiendo…' : 'Manifiesto'}</button>
        <button className="board-tool" onClick={() => void importReferentes()} title="Crear o actualizar el tablero Biblioteca con los referentes de los vídeos"><Library size={14} /> Importar referentes</button>
        <button className="board-tool" onClick={() => gustosInput.current?.click()} title="Sumar los ♥/✕ de un gustos-parcial.json a este proyecto">Importar gustos</button>
        <button className="board-tool" onClick={exportReferentesObsidian} title="Descargar un ZIP con una nota Markdown por referente, con enlaces entre los del mismo marco"><BookOpen size={14} /> Referentes a Obsidian</button>
        <button className="board-tool" onClick={() => importInput.current?.click()}><Upload size={14} /> Importar</button>
        <button className="board-tool" onClick={exportJson}><Download size={14} /> Exportar JSON</button>
        <button className="board-tool" onClick={exportMarkdown}>Obsidian Markdown</button>
        <input ref={importInput} type="file" accept="application/json,.json,text/markdown,.md" hidden onChange={(event) => { void importBoard(event.target.files?.[0]); event.target.value = ''; }} />
        <input ref={mediaInput} type="file" accept="image/*,video/*,audio/*,application/pdf,text/plain,.txt" hidden onChange={(event) => { void addMedia(event.target.files?.[0]); event.target.value = ''; }} />
        <input ref={gustosInput} type="file" accept="application/json,.json" hidden aria-label="Archivo de gustos parciales" onChange={(event) => { void importGustos(event.target.files?.[0]); event.target.value = ''; }} />
      </nav>

      {engineMessage && <div className="board-engine-notice" role="status"><span>{engineMessage}</span>{onRetryEngine && <button className="board-tool" onClick={onRetryEngine}>Reintentar motor PDF</button>}</div>}
      {projectError && <div className="board-alert" role="alert"><span>{projectError} Tus tableros locales siguen disponibles.</span><button type="button" onClick={() => { loadedProjectBoardSignature.current = ''; setProjectError(null); setProjectLoadAttempt((value) => value + 1); }}>Reintentar proyectos</button><button type="button" onClick={() => setProjectError(null)} aria-label="Cerrar aviso"><X size={14} /></button></div>}
      {storageError && (
        <div className="board-alert" role="alert">
          <span>{storageError}. Tus cambios siguen en esta ventana.</span>
          {writes.error && <button type="button" onClick={() => void flushBoardWrites()}>Reintentar guardado</button>}
          <button type="button" onClick={exportJson}>Exportar copia de rescate</button>
          <button type="button" onClick={() => setLoadError(null)} aria-label="Cerrar aviso"><X size={14} /></button>
        </div>
      )}
      {notice && <div className="board-toast" role="status">{notice}<button onClick={() => setNotice(null)} aria-label="Cerrar aviso"><X size={14} /></button></div>}

      {referencesOpen && activeProject && (
        <aside className="board-reference-panel" aria-label={`Referencias PDF de ${activeProject.name}`}>
          <div className="board-reference-heading"><div><strong>Referencias PDF</strong><span>{activeProject.name}</span></div><button className="board-icon-button" onClick={() => setReferencesOpen(false)} aria-label="Cerrar referencias"><X size={15} /></button></div>
          {activeProjectReferences.map((reference) => (
            <article className="board-reference-card" key={reference.id}>
              <strong>{reference.sourceName}</strong>
              <span>Página {reference.page}</span>
              {reference.quote && <blockquote>{reference.quote}</blockquote>}
              {reference.note && <p>{reference.note}</p>}
              <small>SHA-256 · {reference.sourceSha256.slice(0, 12)}…</small>
              <div className="board-reference-actions"><button className="board-tool" onClick={() => handleOpenPdfReference(reference)}>Abrir página</button><button className="board-tool danger" onClick={() => void handleDeletePdfReference(reference)}>Eliminar</button></div>
            </article>
          ))}
        </aside>
      )}

      <main
        ref={viewportRef}
        className={`board-viewport ${isPanning ? 'panning' : ''} ${connectMode ? 'connecting' : ''} ${frameToolId ? 'drawing-frame' : ''}`}
        style={{ backgroundPosition: `${pan.x}px ${pan.y}px`, backgroundSize: `${24 * zoom}px ${24 * zoom}px` }}
        onPointerDown={beginViewportGesture}
        onPointerMove={moveViewportGesture}
        onPointerUp={endViewportGesture}
        onPointerCancel={endViewportGesture}
        onClickCapture={(event) => {
          if (!suppressViewportClick.current) return;
          suppressViewportClick.current = false;
          event.stopPropagation();
          event.preventDefault();
        }}
        onClick={(event) => {
          if (event.target === viewportRef.current) setSelectedCardIds([]);
        }}
      >
        <svg className="board-relations" width={viewportSize.width} height={viewportSize.height} viewBox={`0 0 ${Math.max(1, viewportSize.width)} ${Math.max(1, viewportSize.height)}`} aria-label="Relaciones entre tarjetas">
            <defs><marker id="board-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" /></marker></defs>
            {activeBoard.relations.map((relation) => {
              const from = activeBoard.cards.find((card) => card.id === relation.from);
              const to = activeBoard.cards.find((card) => card.id === relation.to);
              if (!from || !to) return null;
              const a = cardCenter(from);
              const b = cardCenter(to);
              return <line key={relation.id} x1={pan.x + a.x * zoom} y1={pan.y + a.y * zoom} x2={pan.x + b.x * zoom} y2={pan.y + b.y * zoom} markerEnd="url(#board-arrow)" />;
            })}
          </svg>
        <div className="board-stage" style={{ transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})` }}>
          {activeBoard.cards.map((card) => {
            const matches = matchingCards.has(card.id);
            const isConnectionSource = connectFromId === card.id;
            if (card.type === 'marco') {
              const frame = readFrameData(card);
              const childCount = frame.hijos.filter((id) => cardsById.has(id)).length;
              const esEntropia = esMarcoEntropia(card);
              const collage = esEntropia ? leerEntropia(card) : null;
              return (
                <article
                  key={card.id}
                  data-card-id={card.id}
                  data-marco={esEntropia ? 'entropia' : 'libre'}
                  className={`board-frame ${esEntropia ? 'is-entropia' : ''} ${collage?.guardado ? 'is-guardado' : ''} ${frame.vista === 'archivo' ? 'is-archive' : frame.vista === 'muro' ? 'is-muro' : frame.vista === 'mesa' ? 'is-mesa' : ''} ${selectedCardIds.includes(card.id) ? 'selected' : ''} ${!matches ? 'dimmed' : ''}`}
                  style={{ left: card.x, top: card.y, width: card.width, height: frame.alto }}
                  onClick={(event) => handleCardSelection(card.id, event)}
                  onDoubleClick={(event) => {
                    if (frame.vista !== 'archivo') return;
                    const target = event.target as HTMLElement;
                    if (target.closest('input,select,a')) return;
                    const control = target.closest('button');
                    if (control && !control.classList.contains('archivo-zone')) return;
                    event.stopPropagation();
                    setArchiveFullscreenId(card.id);
                  }}
                  onBlurCapture={closeTextGroup}
                >
                  <div className="board-frame-head" onPointerDown={(event) => startCardDrag(card, event)} onPointerMove={moveCardDrag} onPointerUp={endCardDrag} onPointerCancel={endCardDrag} title="Arrastra para mover el marco y sus tarjetas">
                    <span className="board-drag-grip" aria-hidden="true">⠿</span>
                    <input className="board-frame-title" value={card.title} maxLength={200} onChange={(event) => updateCard(card.id, { title: event.target.value })} aria-label="Título del marco" />
                    {!esEntropia && (
                      <label className="board-frame-view">
                        Ver como
                        <select value={frame.vista} onChange={(event) => updateFrameView(card.id, event.target.value as FrameView)} aria-label={`Ver como: ${card.title || 'marco'}`}>
                          <option value="libre">Libre</option>
                          <option value="archivo">Archivo</option>
                          <option value="muro">Muro</option>
                          <option value="mesa">Mesa de luz</option>
                        </select>
                      </label>
                    )}
                    {!esEntropia && (
                      <button
                        className="board-frame-publish"
                        type="button"
                        disabled={publishingFrameId === card.id}
                        onPointerDown={(event) => event.stopPropagation()}
                        onClick={(event) => { event.stopPropagation(); void publishFrame(card); }}
                        title="Publicar esta vista como web local (index.html + style.css + media/)"
                        aria-label={`Publicar ${card.title || 'marco'}`}
                      >{publishingFrameId === card.id ? '…' : 'Publicar'}</button>
                    )}
                    <button className="board-frame-delete" onClick={(event) => { event.stopPropagation(); removeCard(card.id); }} aria-label="Eliminar marco" title="Eliminar el marco y dejar sus tarjetas"><X size={14} /></button>
                  </div>
                  {esEntropia ? (
                    <EntropiaVista
                      datos={collage}
                      fuentes={fuentesEntropia}
                      onTirar={() => tirarEnMarcoEntropia(card)}
                      onOtra={() => tirarEnMarcoEntropia(card, nuevaSemilla())}
                      onLike={() => guardarCollageEntropia(card)}
                      onNope={() => descartarCollageEntropia(card)}
                    />
                  ) : frame.vista === 'archivo' ? (
                    <>
                      <ArchivoView frameTitle={card.title} cards={activeBoard.cards} childIds={frame.hijos} />
                      <div className="board-frame-hint">Doble clic: pantalla completa · Esc para volver</div>
                    </>
                  ) : frame.vista === 'muro' ? (
                    <>
                      <MuroView frameTitle={card.title} cards={activeBoard.cards} childIds={frame.hijos} width={Math.max(180, card.width)} />
                      <div className="board-frame-hint">Clic en una miniatura: caja de luz</div>
                    </>
                  ) : frame.vista === 'mesa' ? (
                    <MesaView frameTitle={card.title} cards={activeBoard.cards} childIds={frame.hijos} width={Math.max(180, card.width)} />
                  ) : (
                    <div className="board-frame-meta">{childCount} {childCount === 1 ? 'tarjeta' : 'tarjetas'} dentro</div>
                  )}
                </article>
              );
            }
            // Los hijos de un marco con vista propia se pintan dentro del marco, no encima.
            if (framedChildIds.has(card.id)) return null;
            return (
              <article
                key={card.id}
                data-card-id={card.id}
                className={`board-card color-${card.color} ${selectedCardIds.includes(card.id) ? 'selected' : ''} ${!matches ? 'dimmed' : ''} ${isConnectionSource ? 'connection-source' : ''}`}
                style={{ left: card.x, top: card.y, width: card.width }}
                onClick={(event) => {
                  if (connectMode) {
                    const target = event.target as HTMLElement;
                    if (target.closest('input,textarea,button,a,video,audio')) return;
                    handleConnectCard(card.id);
                  } else handleCardSelection(card.id, event);
                }}
                onPointerEnter={card.type === 'referente' ? () => { hoveredReferenteId.current = card.id; } : undefined}
                onPointerLeave={card.type === 'referente' ? () => {
                  if (hoveredReferenteId.current === card.id) hoveredReferenteId.current = null;
                } : undefined}
                onBlurCapture={closeTextGroup}
              >
                <div className="board-card-head" onPointerDown={(event) => startCardDrag(card, event)} onPointerMove={moveCardDrag} onPointerUp={endCardDrag} onPointerCancel={endCardDrag} title="Arrastra para mover la tarjeta">
                  <span className="board-drag-grip" aria-hidden="true">⠿</span>
                  <input className="board-card-title" value={card.title} maxLength={200} onChange={(event) => updateCard(card.id, { title: event.target.value })} aria-label="Título de tarjeta" />
                  <button className={`board-connect-button ${connectMode ? 'visible' : ''}`} onClick={(event) => { event.stopPropagation(); handleConnectCard(card.id); }} title="Elegir para relacionar" aria-label="Relacionar esta tarjeta"><Link2 size={13} /></button>
                  <button className="board-card-delete" onClick={(event) => { event.stopPropagation(); removeCard(card.id); }} aria-label="Eliminar tarjeta"><X size={14} /></button>
                </div>
                <div className="board-card-color-row" aria-label="Color de tarjeta">
                  {COLORS.map((color) => <button key={color} className={`board-color-swatch ${color} ${card.color === color ? 'current' : ''}`} onClick={() => updateCard(card.id, { color })} aria-label={`Color ${color}`} aria-pressed={card.color === color} />)}
                </div>
                <BoardCardContent card={card} editar={replaceCard} />
              </article>
            );
          })}
          {frameDraft && (
            <div
              className="board-frame-draft"
              style={{ left: frameDraft.x, top: frameDraft.y, width: frameDraft.width, height: frameDraft.height }}
              aria-hidden="true"
            />
          )}
          {activeBoard.cards.length === 0 && (
            <div className="board-empty" style={{ left: (viewportSize.width / 2 - pan.x) / zoom - 170, top: (viewportSize.height / 2 - pan.y) / zoom - 60 }}>
              <strong>Tu espacio de ideas está listo</strong>
              <span>Agrega una nota, enlace o archivo para empezar.</span>
              <button onClick={() => addToolCard('note')}><Plus size={14} /> Crear primera nota</button>
            </div>
          )}
        </div>

        <div className="board-zoom-controls" aria-label="Controles de vista">
          <button onClick={() => zoomBy(1.15)} aria-label="Acercar"><ZoomIn size={16} /></button>
          <span>{Math.round(zoom * 100)}%</span>
          <button onClick={() => zoomBy(1 / 1.15)} aria-label="Alejar"><ZoomOut size={16} /></button>
          <button onClick={fitBoard} aria-label="Ajustar tablero" title="Ajustar todas las tarjetas">Ajustar</button>
        </div>
        <div className="board-count">{activeBoard.cards.length} {activeBoard.cards.length === 1 ? 'tarjeta' : 'tarjetas'} · arrastra el fondo para moverte · ⌘/Ctrl + rueda para acercar</div>
      </main>

      {archiveFullscreenFrame && (
        <div className="board-archive-fullscreen" role="dialog" aria-modal="true" aria-label={`Archivo a pantalla completa: ${archiveFullscreenFrame.title || 'marco'}`}>
          <button type="button" className="archivo-fullscreen-close" onClick={() => setArchiveFullscreenId(null)}>Esc · volver a la pizarra</button>
          <ArchivoView
            frameTitle={archiveFullscreenFrame.title}
            cards={activeBoard.cards}
            childIds={readFrameData(archiveFullscreenFrame).hijos}
            fullscreen
          />
        </div>
      )}

      {selectedCards.length > 1 ? (
        <aside className="board-selection" aria-live="polite">{selectedCards.length} tarjetas seleccionadas</aside>
      ) : selectedCard ? (
        <aside className="board-selection" aria-live="polite">Seleccionada: <strong>{selectedCard.title || 'Sin título'}</strong></aside>
      ) : null}

      {mirarOpen && (
        <MirarDialog
          boards={boards}
          activeBoardId={activeBoard.id}
          tableroNombre={activeBoard.title}
          proyecto={activeProject?.name || 'Proyecto general'}
          onClose={() => setMirarOpen(false)}
          onAceptar={aceptarLecturaEnReferente}
        />
      )}

      {addMenuOpen && (
        <div
          className="board-add-backdrop"
          onMouseDown={(event) => { if (event.target === event.currentTarget) setAddMenuOpen(false); }}
        >
          <div className="board-add-panel" role="presentation">
            <div className="board-add-heading">
              <span>Añadir tarjeta</span>
              <button type="button" onClick={() => setAddMenuOpen(false)} aria-label="Cerrar menú"><X size={15} /></button>
            </div>
            <BoardToolMenu onChoose={chooseTool} />
          </div>
        </div>
      )}

      {linkDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setLinkDialog(false); }}>
          <form className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="board-link-title" onSubmit={saveLinkCard}>
            <div className="board-dialog-heading"><h2 id="board-link-title">Añadir enlace</h2><button type="button" onClick={() => setLinkDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <label>Título<input autoFocus value={linkTitle} onChange={(event) => setLinkTitle(event.target.value)} placeholder="Nombre de la referencia" /></label>
            <label>Dirección web<input type="url" required value={linkUrl} onChange={(event) => setLinkUrl(event.target.value)} placeholder="https://…" /></label>
            {linkError && <p className="board-dialog-error" role="alert">{linkError}</p>}
            <div className="board-dialog-actions"><button type="button" className="board-tool" onClick={() => setLinkDialog(false)}>Cancelar</button><button type="submit" className="board-tool primary">Agregar enlace</button></div>
          </form>
        </div>
      )}

      {projectDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setProjectDialog(false); }}>
          <form className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="project-dialog-title" onSubmit={(event) => { void handleCreateProject(event); }}>
            <div className="board-dialog-heading"><h2 id="project-dialog-title">Crear proyecto</h2><button type="button" onClick={() => setProjectDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">Agrupa tableros y referencias PDF. Los archivos originales permanecen en su ubicación.</p>
            <label>Nombre del proyecto<input autoFocus required maxLength={120} value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Por ejemplo, Investigación" /></label>
            <div className="board-dialog-actions"><button type="button" className="board-tool" onClick={() => setProjectDialog(false)}>Cancelar</button><button type="submit" className="board-tool primary">Crear proyecto</button></div>
          </form>
        </div>
      )}

      {pdfReferenceDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setPdfReferenceDialog(false); }}>
          <form className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="pdf-reference-title" onSubmit={(event) => { void handleSavePdfReference(event); }}>
            <div className="board-dialog-heading"><h2 id="pdf-reference-title">Referenciar página PDF</h2><button type="button" onClick={() => setPdfReferenceDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">{pdfReferenceSource?.filename ?? 'Sin PDF abierto'} · página {pdfReferenceSource?.page ?? '—'}</p>
            <p className="board-dialog-hint">Se guarda el nombre, página y huella del PDF, junto con tu nota. El PDF no se copia.</p>
            <label>Cita o fragmento<textarea maxLength={2000} value={pdfReferenceQuote} onChange={(event) => setPdfReferenceQuote(event.target.value)} rows={4} placeholder="Fragmento que quieres recordar" /></label>
            <label>Nota<textarea maxLength={3000} value={pdfReferenceNote} onChange={(event) => setPdfReferenceNote(event.target.value)} rows={4} placeholder="Por qué es importante para el proyecto" /></label>
            <div className="board-dialog-actions"><button type="button" className="board-tool" onClick={() => setPdfReferenceDialog(false)}>Cancelar</button><button type="submit" className="board-tool primary">Guardar referencia</button></div>
          </form>
        </div>
      )}
    </div>
  );
};
