import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft,
  Archive,
  ChevronDown,
  FolderPlus,
  History,
  Hand,
  Magnet,
  Download,
  LayoutTemplate,
  Library,
  Link2,
  List,
  Lock,
  LockOpen,
  Pencil,
  Plus,
  Search,
  Trash2,
  Undo2,
  Upload,
  Redo2,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import {
  boardFilename,
  boardToMarkdown,
  cloneBoardForImport,
  createBoard,
  duplicateCards,
  isSafeExternalUrl,
  makeBoardExport,
  markdownToBoard,
  MAX_MEDIA_BYTES,
  newBoardId,
  normalizeBoard,
  parseBoardImport,
  type BoardCard,
  type BoardDocument,
  type BoardMedia,
  type BoardRelation,
} from '../board/model';
import { geometriaConector, rectDeTarjeta } from '../board/conectores';
import { vecinoGeometrico, type Direccion } from '../board/navegacion';
import { coincideBusqueda, ordenDePintado, ventanaVirtual, INDICE_ROW_HEIGHT } from '../board/indice';
import { readColumnData, setColumnFolded, columnChildIds } from '../board/columnas';
import { normalizarVistaPrevia } from '../board/vistaPrevia';
import { borrarPlantillasLegacy, crearPlantilla, leerPlantillasLegacy, listarPlantillas, materializar, type Plantilla } from '../board/plantillas';
import { ABRIR_TABLERO_EVENT } from '../board/tools/tablero';
import { studioApi } from '../api/client';
import { factorDePellizco, fitBoardCamera, zoomAtPoint, screenToWorld } from '../board/camera';
import { movimientoReducido, pasoInercia, velocidadDeMuestras, type MuestraInercia } from '../motion/muelle';
import { alignCards, distributeCards, snapPosition, type Alignment, type CardSize, type DistributionAxis } from '../board/geometry';
import { imanDeCaja, inclinacionPorVelocidad, type GuiasIman } from '../board/iman';
import { esMediaLibre, medirMedio } from '../board/medio';
import {
  cardsInsideFrame,
  FRAME_MIN_SIZE,
  readFrameData,
  rectFromPoints,
  setFrameView,
  type FrameRect,
  type FrameView,
} from '../board/frames';
import { emptyBoardHistory, recordBoardChange, redoBoardChange, undoBoardChange, type BoardHistory } from '../board/history';
import {
  atajoParaEvento,
  esObjetivoDeTexto,
  gruposDeAyuda,
  textoAtajo,
  type AtajoLienzo,
} from '../board/atajos';
import {
  alternarEnSeleccion,
  aplicarMarquesina,
  borrarTarjetas,
  claveDeRafaga,
  duplicarSeleccion,
  moverTarjetas,
  reordenarTarjetas,
  seleccionarTodoElTablero,
  tarjetasAMover,
} from '../board/seleccion';
import {
  copiarTarjetas,
  esMarcaDeTarjetas,
  hayTarjetasCopiadas,
  pegarTarjetas,
} from '../board/portapapeles';
import { agregarImagenDesdeUrl, importarBiblioteca } from '../board/referentes/biblioteca';
import { construirZipObsidian, notasObsidian } from '../board/referentes/historial';
import { aceptarLectura } from '../board/referentes/mirar';
import { leerReferente, type Lectura } from '../board/referentes/model';
import { loadBoardWorkspace } from '../board/storage';
import { guardarHistorial, leerHistoriales, listarBorrados, olvidarBorrado, recordarBorrado, tomarBorrado, type BorradoEntry, type BorradoKind } from '../board/memoria';
import { BoardToolMenu } from '../board/tools/menu';
import { DESIGN_SYSTEMS, normalizeDesignSystem, type DesignSystemId } from '../board/diseno';
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
  addProjectPlantillas,
  assignBoardToProject,
  createProject,
  deletePdfReference,
  deleteProjectPlantilla,
  loadProjectWorkspace,
  removeBoardProjectLink,
  renameProject,
  savePdfReference,
  saveProjectGustos,
  saveProjectPlantilla,
  setActiveProject,
} from '../board/projectStorage';
import { useBoardWrites } from '../hooks/useBoardWrites';
import { BoardCardItem } from './BoardCardItem';
import { BoardColumn } from './BoardColumn';
import { BoardFreeMedia, type EsquinaMedia } from './BoardFreeMedia';
import { TituloEnSitio } from './InlineEdit';
import { useFocusTrap } from './useFocusTrap';
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
const RAIL_TOOLS = ['note', 'link', 'media', 'tareas', 'columna', 'referente', 'marco', 'entropia'];
const ETIQUETA_BORRADO: Record<BorradoKind, string> = {
  board: 'Tablero',
  reference: 'Referencia PDF',
  cards: 'Tarjetas',
  project: 'Proyecto',
};

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => (typeof reader.result === 'string' ? resolve(reader.result) : reject(new Error('No se pudo leer el archivo.')));
    reader.onerror = () => reject(new Error('No se pudo leer el archivo.'));
    reader.readAsDataURL(file);
  });
}

function liberarPuntero(element: HTMLElement | null, pointerId: number): void {
  if (!element) return;
  try {
    if (element.hasPointerCapture(pointerId)) element.releasePointerCapture(pointerId);
  } catch {
    /* el elemento ya no existe o el puntero se soltó solo */
  }
}

/** Normaliza deltaMode (píxel, línea o página) a píxeles de pantalla. */
function deltaDeRueda(event: WheelEvent, altoViewport: number): { x: number; y: number } {
  const escala = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? altoViewport : 1;
  return { x: event.deltaX * escala, y: event.deltaY * escala };
}

function downloadText(filename: string, content: string, mimeType: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

interface Modificadores {
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
}

interface GestoWebKit extends Event {
  scale?: number;
  clientX?: number;
  clientY?: number;
}

interface CardHandlers {
  select: (cardId: string, event: Modificadores) => void;
  connect: (cardId: string) => void;
  connectStart: (card: BoardCard, event: React.PointerEvent<HTMLElement>) => void;
  dragStart: (card: BoardCard, event: React.PointerEvent<HTMLElement>) => void;
  dragMove: (event: React.PointerEvent<HTMLElement>) => void;
  dragEnd: (event: React.PointerEvent<HTMLElement>) => void;
  delete: (cardId: string) => void;
  patch: (cardId: string, patch: Partial<BoardCard>) => void;
  replace: (card: BoardCard) => void;
  hover: (cardId: string, over: boolean) => void;
  blur: () => void;
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
  const [renamingProject, setRenamingProject] = useState(false);
  const [projectDraft, setProjectDraft] = useState('');
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [spacePanActive, setSpacePanActive] = useState(false);
  const spaceHeld = useRef(false);
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
  /** Tirador de conector: tarjeta de origen y puntero en coordenadas de pantalla. */
  const [connectDraft, setConnectDraft] = useState<{ from: string; x: number; y: number; mundo: { x: number; y: number }; target: string | null } | null>(null);
  const [marquee, setMarquee] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const [nestedDialog, setNestedDialog] = useState(false);
  const [templateDialog, setTemplateDialog] = useState(false);
  const [templates, setTemplates] = useState<Plantilla[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  /** Aviso de borrado con deshacer: la red de seguridad es el historial, no un diálogo. */
  const [aviso, setAviso] = useState<{ texto: string; deshacer?: () => void; historial?: boolean } | null>(null);
  const avisoTimer = useRef<number | null>(null);
  /** El listener se registra una vez; cada render actualiza el despachador con el estado vigente. */
  const ejecutarAtajoRef = useRef<(atajo: AtajoLienzo, event: KeyboardEvent) => void>(() => {});
  const [search, setSearch] = useState('');
  const [searchScope, setSearchScope] = useState<'tablero' | 'proyecto' | 'biblioteca'>('tablero');
  const [searchActivo, setSearchActivo] = useState(0);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [indexOpen, setIndexOpen] = useState(false);
  const [indexQuery, setIndexQuery] = useState('');
  const [indexScroll, setIndexScroll] = useState(0);
  const indexSearchRef = useRef<HTMLInputElement>(null);
  const pendingCentro = useRef<{ boardId: string; cardId: string } | null>(null);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [libraryMenuOpen, setLibraryMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const libraryMenuRef = useRef<HTMLDivElement>(null);
  const [linkDialog, setLinkDialog] = useState(false);
  const [linkTitle, setLinkTitle] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkError, setLinkError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [snapEnabled, setSnapEnabled] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  /** Modo Mano: un dedo o el ratón mueven el mundo sin dibujar marquesina. */
  const [handMode, setHandMode] = useState(false);
  const [guias, setGuias] = useState<GuiasIman>({});
  const [viewportSize, setViewportSize] = useState({ width: 0, height: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const relationsRef = useRef<SVGGElement>(null);
  const boardsRef = useRef<BoardDocument[]>([]);
  const activeBoardRef = useRef<BoardDocument | null>(null);
  const zoomValueRef = useRef<HTMLButtonElement>(null);
  const cameraRef = useRef({ pan: { x: 0, y: 0 }, zoom: 1 });
  const paintRaf = useRef(0);
  const inertiaRaf = useRef(0);
  const syncTimer = useRef<number | null>(null);
  /** Timer que retira `.gesto-activo` cuando dejan de llegar eventos de gesto. */
  const gestoVisualTimer = useRef<number | null>(null);
  const panDrag = useRef<{ pointerId: number; x: number; y: number; panX: number; panY: number; samples: MuestraInercia[]; captureEl: HTMLElement | null } | null>(null);
  const cardDrag = useRef<{ pointerId: number; boardId: string; ids: string[]; x: number; y: number; positions: Map<string, { x: number; y: number }>; sizes: Map<string, CardSize>; startBoard: BoardDocument; gesture: string; moved: boolean; captureEl: HTMLElement | null; lastX: number; lastY: number; lastT: number; altKey: boolean; duplicated: boolean } | null>(null);
  /** Rectángulo de selección (arrastrar el fondo), en coordenadas de pantalla. */
  const marqueeDrag = useRef<{ pointerId: number; startX: number; startY: number; captureEl: HTMLElement | null; modo: 'reemplazar' | 'sumar' | 'restar' } | null>(null);
  /** H3 · dedos activos y gesto táctil: un dedo dibuja, dos panean y pellizcan. */
  const touchPoints = useRef(new Map<number, { x: number; y: number }>());
  const touchGesture = useRef<{
    mode: 'marquee' | 'camera';
    baseCamera?: { pan: { x: number; y: number }; zoom: number };
    baseDist?: number;
    baseMid?: { x: number; y: number };
  } | null>(null);
  const touchIgnore = useRef(false);
  const connectOrigin = useRef<{ cardId: string; pointerId: number } | null>(null);
  /** Herramienta de marco elegida en el menú: el siguiente arrastre dibuja el rectángulo. */
  const [frameToolId, setFrameToolId] = useState<string | null>(null);
  const [frameDraft, setFrameDraft] = useState<FrameRect | null>(null);
  const [draggingIds, setDraggingIds] = useState<string[]>([]);
  const [settlingIds, setSettlingIds] = useState<string[]>([]);
  const [dropFrameId, setDropFrameId] = useState<string | null>(null);
  const dropFrameIdRef = useRef<string | null>(null);
  const frameResize = useRef<{ pointerId: number; cardId: string; startX: number; startY: number; width: number; height: number; startBoard: BoardDocument; captureEl: HTMLElement | null; elemento: HTMLElement | null; raf: number; ultimo: { width: number; height: number } } | null>(null);
  const freeResize = useRef<{ pointerId: number; cardId: string; corner: EsquinaMedia; startX: number; startY: number; x: number; y: number; width: number; height: number; ratio: number; startBoard: BoardDocument; captureEl: HTMLElement | null; elemento: HTMLElement | null; raf: number; ultimo: { x: number; y: number; width: number; height: number } | null } | null>(null);
  const settleTimer = useRef<number | null>(null);
  const frameDraw = useRef<{ pointerId: number; start: { x: number; y: number }; captureEl: HTMLElement | null } | null>(null);
  const wheelHandlerRef = useRef<(event: WheelEvent) => void>(() => {});
  /** Marco abierto a pantalla completa en la vista Archivo; Esc vuelve a la pizarra. */
  const [archiveFullscreenId, setArchiveFullscreenId] = useState<string | null>(null);
  /** Marco cuya publicación local se está escribiendo (bloquea el botón mientras dura). */
  const [publishingFrameId, setPublishingFrameId] = useState<string | null>(null);
  /** El manifiesto semanal espera al motor local; el botón no se dispara dos veces. */
  const [manifesting, setManifesting] = useState(false);
  const [boardHistories, setBoardHistories] = useState<Record<string, BoardHistory>>({});
  /** «nueva» declara que no había historial que restaurar; «restaurada» que sí. */
  const [historyStatus, setHistoryStatus] = useState<'nueva' | 'restaurada'>('nueva');
  const historiesReady = useRef(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [borrados, setBorrados] = useState<BorradoEntry[]>([]);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
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
  const cardHandlers = useRef<CardHandlers | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const algunDialogoAbierto = shortcutsOpen || nestedDialog || templateDialog || linkDialog || projectDialog || pdfReferenceDialog || archiveOpen || Boolean(archiveFullscreenId);
  useFocusTrap(algunDialogoAbierto, dialogRef);

  const projectBoards = activeProjectId
    ? boards.filter((board) => projectIdByBoardId.get(board.id) === activeProjectId)
    : boards;
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? null;
  const activeProjectReferences = projectReferences.filter((reference) => reference.projectId === activeProjectId);
  const activeBoard = projectBoards.find((board) => board.id === activeBoardId) ?? projectBoards[0] ?? null;
  const selectedCards = activeBoard?.cards.filter((card) => selectedCardIds.includes(card.id)) ?? [];
  const activeHistory = activeBoard ? boardHistories[activeBoard.id] ?? emptyBoardHistory() : emptyBoardHistory();
  const canUndo = activeHistory.undo.length > 0;
  const canRedo = activeHistory.redo.length > 0;

  const cardsById = useMemo(() => new Map((activeBoard?.cards ?? []).map((card) => [card.id, card])), [activeBoard]);
  /** Hijos que ya se pintan dentro de un marco con vista propia: no se dibujan dos veces. */
  const framedChildIds = useMemo(() => {
    const ids = new Set<string>();
    for (const card of activeBoard?.cards ?? []) {
      if (card.type === 'columna') {
        for (const id of readColumnData(card).hijos) ids.add(id);
        continue;
      }
      if (card.type !== 'marco' || readFrameData(card).vista === 'libre') continue;
      for (const id of readFrameData(card).hijos) ids.add(id);
    }
    for (const id of columnChildIds(activeBoard?.cards ?? [])) ids.add(id);
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
    Promise.all([loadBoardWorkspace(), leerHistoriales()])
      .then(([snapshot, historiales]) => {
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
        const ids = new Set(snapshot.boards.map((board) => board.id));
        const restaurados = Object.fromEntries(
          Object.entries(historiales).filter(([boardId]) => ids.has(boardId)),
        );
        if (Object.keys(restaurados).length > 0) {
          setBoardHistories(restaurados);
          setHistoryStatus('restaurada');
        } else {
          setHistoryStatus('nueva');
        }
        historiesReady.current = true;
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

  // El historial de deshacer sobrevive a recargar. Se escribe con pausa y por
  // tablero activo: guardar la copia de los 500 tableros en cada gesto sería peor
  // que el problema que resuelve.
  useEffect(() => {
    if (!loaded || !historiesReady.current || !activeBoardId) return;
    const timer = window.setTimeout(() => {
      const history = boardHistories[activeBoardId];
      if (history) void guardarHistorial(activeBoardId, history);
    }, 600);
    return () => window.clearTimeout(timer);
  }, [activeBoardId, boardHistories, loaded]);

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
      return [[id, { width: bounds.width / cameraRef.current.zoom, height: bounds.height / cameraRef.current.zoom }] as const];
    }));
  }, []);

  const aplicarCamara = useCallback(() => {
    const { pan: posicion, zoom: escala } = cameraRef.current;
    const stage = stageRef.current;
    if (stage) {
      stage.style.transform = `translate3d(${posicion.x}px, ${posicion.y}px, 0) scale(${escala})`;
      stage.dataset.lod = escala < 0.35 ? 'min' : 'full';
    }
    const viewport = viewportRef.current;
    if (viewport) {
      viewport.style.backgroundPosition = `${posicion.x}px ${posicion.y}px`;
      viewport.style.backgroundSize = `${GRID_SIZE * escala}px ${GRID_SIZE * escala}px`;
    }
    relationsRef.current?.setAttribute('transform', `translate(${posicion.x} ${posicion.y}) scale(${escala})`);
    if (zoomValueRef.current) {
      zoomValueRef.current.textContent = `${Math.round(escala * 100)}%`;
      zoomValueRef.current.setAttribute('aria-label', `Zoom ${Math.round(escala * 100)} por ciento, ajustar tablero`);
    }
  }, []);

  const pintarCamara = useCallback(() => {
    if (paintRaf.current) return;
    paintRaf.current = requestAnimationFrame(() => {
      paintRaf.current = 0;
      aplicarCamara();
    });
  }, [aplicarCamara]);

  const sincronizarCamara = useCallback(() => {
    if (syncTimer.current) {
      window.clearTimeout(syncTimer.current);
      syncTimer.current = null;
    }
    setPan(cameraRef.current.pan);
    setZoom(cameraRef.current.zoom);
  }, []);

  const programarSincronizacion = useCallback(() => {
    if (syncTimer.current) window.clearTimeout(syncTimer.current);
    syncTimer.current = window.setTimeout(() => {
      syncTimer.current = null;
      sincronizarCamara();
    }, 150);
  }, [sincronizarCamara]);

  /**
   * Mientras hay gesto, ninguna transición CSS puede tocar transform/scale de las
   * tarjetas ni del mundo. La clase vive en el DOM (no en React) para no re-renderizar.
   */
  const marcarGestoVisual = useCallback((duracionMs = 0) => {
    viewportRef.current?.classList.add('gesto-activo');
    if (gestoVisualTimer.current) {
      window.clearTimeout(gestoVisualTimer.current);
      gestoVisualTimer.current = null;
    }
    if (duracionMs > 0) {
      gestoVisualTimer.current = window.setTimeout(() => {
        gestoVisualTimer.current = null;
        viewportRef.current?.classList.remove('gesto-activo');
      }, duracionMs);
    }
  }, []);

  const terminarGestoVisual = useCallback(() => {
    if (gestoVisualTimer.current) {
      window.clearTimeout(gestoVisualTimer.current);
      gestoVisualTimer.current = null;
    }
    viewportRef.current?.classList.remove('gesto-activo');
  }, []);

  const detenerInercia = useCallback(() => {
    if (inertiaRaf.current) {
      cancelAnimationFrame(inertiaRaf.current);
      inertiaRaf.current = 0;
    }
  }, []);

  const iniciarInercia = useCallback((vx: number, vy: number) => {
    detenerInercia();
    if (movimientoReducido() || Math.hypot(vx, vy) < 80) return;
    let estado = { x: cameraRef.current.pan.x, y: cameraRef.current.pan.y, vx, vy };
    let ultimo = performance.now();
    const paso = (ahora: number) => {
      const dt = Math.min(0.05, Math.max(0, (ahora - ultimo) / 1000));
      ultimo = ahora;
      estado = pasoInercia(estado, dt);
      cameraRef.current = { ...cameraRef.current, pan: { x: estado.x, y: estado.y } };
      pintarCamara();
      if (estado.vx !== 0 || estado.vy !== 0) inertiaRaf.current = requestAnimationFrame(paso);
      else {
        inertiaRaf.current = 0;
        programarSincronizacion();
      }
    };
    inertiaRaf.current = requestAnimationFrame(paso);
  }, [detenerInercia, pintarCamara, programarSincronizacion]);

  const limpiarInclinacion = useCallback(() => {
    viewportRef.current?.style.removeProperty('--drag-tilt');
  }, []);

  /** Un gesto nuevo o una pérdida de foco no deja capturas, clases ni timers colgados. */
  const cancelarGestos = useCallback(() => {
    detenerInercia();
    if (gestoVisualTimer.current) {
      window.clearTimeout(gestoVisualTimer.current);
      gestoVisualTimer.current = null;
    }
    if (settleTimer.current) {
      window.clearTimeout(settleTimer.current);
      settleTimer.current = null;
    }
    const pan = panDrag.current;
    if (pan) liberarPuntero(pan.captureEl, pan.pointerId);
    const card = cardDrag.current;
    if (card) liberarPuntero(card.captureEl, card.pointerId);
    const draw = frameDraw.current;
    if (draw) liberarPuntero(draw.captureEl, draw.pointerId);
    const resize = frameResize.current;
    if (resize) {
      liberarPuntero(resize.captureEl, resize.pointerId);
      if (resize.raf) cancelAnimationFrame(resize.raf);
      if (resize.elemento) {
        resize.elemento.style.width = `${resize.width}px`;
        resize.elemento.style.height = `${resize.height}px`;
      }
    }
    const free = freeResize.current;
    if (free) {
      liberarPuntero(free.captureEl, free.pointerId);
      if (free.raf) cancelAnimationFrame(free.raf);
      if (free.elemento) {
        free.elemento.style.left = `${free.x}px`;
        free.elemento.style.top = `${free.y}px`;
        free.elemento.style.width = `${free.width}px`;
        free.elemento.style.height = `${free.height}px`;
      }
    }
    const marquesina = marqueeDrag.current;
    if (marquesina) liberarPuntero(marquesina.captureEl, marquesina.pointerId);
    panDrag.current = null;
    cardDrag.current = null;
    frameDraw.current = null;
    frameResize.current = null;
    freeResize.current = null;
    marqueeDrag.current = null;
    touchPoints.current.clear();
    touchGesture.current = null;
    touchIgnore.current = false;
    connectOrigin.current = null;
    setConnectDraft(null);
    setIsPanning(false);
    setDraggingIds([]);
    setSettlingIds([]);
    setDropFrameId(null);
    dropFrameIdRef.current = null;
    setFrameDraft(null);
    setMarquee(null);
    setGuias({});
    limpiarInclinacion();
    terminarGestoVisual();
  }, [detenerInercia, limpiarInclinacion, terminarGestoVisual]);

  useLayoutEffect(() => {
    aplicarCamara();
  });

  // Los guardados asíncronos (vista previa, lectura, referente) necesitan el tablero más reciente,
  // no el de la renderización en la que se lanzó la petición.
  useLayoutEffect(() => {
    boardsRef.current = boards;
    activeBoardRef.current = activeBoard;
  }, [activeBoard, boards]);

  useEffect(() => () => {
    if (paintRaf.current) cancelAnimationFrame(paintRaf.current);
    if (inertiaRaf.current) cancelAnimationFrame(inertiaRaf.current);
    if (syncTimer.current) window.clearTimeout(syncTimer.current);
    if (gestoVisualTimer.current) window.clearTimeout(gestoVisualTimer.current);
  }, []);

  // El tablero cambia de vista o de documento: nada del gesto anterior debe sobrevivir.
  useEffect(() => () => cancelarGestos(), [activeBoard?.id, archiveFullscreenId, cancelarGestos]);

  // Red de seguridad para cuando el pointerup ocurre fuera de la ventana o el WebView pierde el foco.
  useEffect(() => {
    const alSoltar = () => {
      if (panDrag.current || cardDrag.current || frameDraw.current || frameResize.current || marqueeDrag.current) cancelarGestos();
    };
    const alOcultar = () => { if (document.hidden) alSoltar(); };
    window.addEventListener('pointerup', alSoltar);
    window.addEventListener('pointercancel', alSoltar);
    window.addEventListener('blur', alSoltar);
    document.addEventListener('visibilitychange', alOcultar);
    return () => {
      window.removeEventListener('pointerup', alSoltar);
      window.removeEventListener('pointercancel', alSoltar);
      window.removeEventListener('blur', alSoltar);
      document.removeEventListener('visibilitychange', alOcultar);
    };
  }, [cancelarGestos]);

  const centerCamera = useCallback((board: BoardDocument | null) => {
    const { width, height } = viewportSize;
    if (!width || !height) return;
    const camera = fitBoardCamera(board?.cards ?? [], { width, height }, measureCardSizes());
    cameraRef.current = camera;
    aplicarCamara();
    setZoom(camera.zoom);
    setPan(camera.pan);
  }, [aplicarCamara, measureCardSizes, viewportSize]);

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

  // Las plantillas guardadas ya no viven en localStorage global: la primera vez que
  // aparece un proyecto se mueven a su registro y se borra la copia antigua.
  const migratedTemplates = useRef(false);
  useEffect(() => {
    if (!loaded || !activeProject || migratedTemplates.current) return;
    const legacy = leerPlantillasLegacy();
    if (legacy.length === 0) return;
    migratedTemplates.current = true;
    const projectId = activeProject.id;
    void (async () => {
      try {
        const plantillas = await addProjectPlantillas(projectId, legacy);
        borrarPlantillasLegacy();
        setProjects((current) => current.map((project) => project.id === projectId ? { ...project, plantillas } : project));
        setTemplates(listarPlantillas(plantillas));
        setNotice(`${legacy.length} ${legacy.length === 1 ? 'plantilla guardada se movió' : 'plantillas guardadas se movieron'} a «${activeProject.name}».`);
      } catch (error) {
        migratedTemplates.current = false;
        setProjectError(error instanceof Error ? error.message : 'No se pudieron mover las plantillas al proyecto.');
      }
    })();
  }, [activeProject, loaded]);

  // El sistema de diseño del tablero se aplica en la raíz para que alcance
  // también a los portales (pliego, caja de luz, diálogos), no solo al lienzo.
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.designSystem = normalizeDesignSystem(activeBoard?.sistema);
    return () => {
      delete root.dataset.designSystem;
    };
  }, [activeBoard?.id, activeBoard?.sistema]);

  // Un tablero anidado pide abrirse desde su tarjeta (botón o doble clic).
  useEffect(() => {
    const abrir = (event: Event) => {
      const boardId = (event as CustomEvent<{ boardId?: string }>).detail?.boardId;
      if (!boardId) return;
      const destino = boards.find((board) => board.id === boardId);
      if (!destino) {
        setNotice('Ese tablero anidado ya no existe. La tarjeta conserva su referencia.');
        return;
      }
      void (async () => {
        const guardado = await flushBoardWrites();
        if (!guardado) {
          setNotice('No se abrió el tablero anidado porque el actual aún no se pudo guardar.');
          return;
        }
        const proyecto = projectIdByBoardId.get(boardId);
        if (proyecto && proyecto !== activeProjectId) {
          try {
            await setActiveProject(proyecto);
            setActiveProjectId(proyecto);
          } catch {
            /* El tablero se abre igual: el vínculo de proyecto no bloquea la lectura. */
          }
        }
        setActiveBoardId(boardId);
        setSelectedCardIds([]);
      })();
    };
    window.addEventListener(ABRIR_TABLERO_EVENT, abrir);
    return () => window.removeEventListener(ABRIR_TABLERO_EVENT, abrir);
  }, [activeProjectId, boards, projectIdByBoardId]);

  const updateBoard = useCallback((
    mutate: (board: BoardDocument) => BoardDocument,
    options: { recordHistory?: boolean; coalesceKey?: string } = {},
  ) => {
    const actual = activeBoardRef.current ?? boardsRef.current.find((board) => board.id === activeBoardId);
    if (!actual) return;
    const nextBoard = { ...mutate(actual), updatedAt: new Date().toISOString() };
    if (options.recordHistory !== false) {
      setBoardHistories((current) => ({
        ...current,
        [actual.id]: recordBoardChange(current[actual.id] ?? emptyBoardHistory(), actual, nextBoard, options.coalesceKey),
      }));
    }
    activeBoardRef.current = nextBoard;
    boardsRef.current = boardsRef.current.length
      ? boardsRef.current.map((board) => board.id === nextBoard.id ? nextBoard : board)
      : [nextBoard];
    enqueueBoardSave(nextBoard);
    setBoards(boardsRef.current);
  }, [activeBoardId]);

  /** Una lectura aceptada puede caer en la Biblioteca aunque el tablero abierto sea otro. */
  const updateBoardById = useCallback((
    boardId: string,
    mutate: (board: BoardDocument) => BoardDocument,
    options: { recordHistory?: boolean; coalesceKey?: string } = {},
  ) => {
    const target = boardsRef.current.find((board) => board.id === boardId);
    if (!target) return;
    const nextBoard = { ...mutate(target), updatedAt: new Date().toISOString() };
    if (options.recordHistory !== false) {
      setBoardHistories((current) => ({
        ...current,
        [boardId]: recordBoardChange(current[boardId] ?? emptyBoardHistory(), target, nextBoard, options.coalesceKey),
      }));
    }
    boardsRef.current = boardsRef.current.map((board) => board.id === boardId ? nextBoard : board);
    if (activeBoardRef.current?.id === boardId) activeBoardRef.current = nextBoard;
    enqueueBoardSave(nextBoard);
    setBoards(boardsRef.current);
  }, []);

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
  const addToolCard = useCallback((toolId: string, configure?: (card: BoardCard) => void, at?: { x: number; y: number }): BoardCard | null => {
    const tool = getBoardTool(toolId);
    if (!activeBoard) return null;
    // El tablero más reciente: dos altas seguidas no deben colocar la segunda
    // usando la lista de tarjetas anterior.
    const boardActual = activeBoardRef.current ?? activeBoard;
    if (frameToolId) setNotice(null);
    setFrameToolId(null);
    setFrameDraft(null);
    frameDraw.current = null;
    if (!tool) {
      setNotice(`La herramienta «${toolId}» no está instalada.`);
      return null;
    }
    const destino = at ?? screenToWorld({ x: viewportSize.width / 2, y: viewportSize.height / 2 }, cameraRef.current);
    let x = destino.x - 130;
    let y = destino.y - 90;
    const prototipo = tool.crear(0, 0) as BoardCard;
    const ancho = prototipo.width || 260;
    const alto = prototipo.type === 'marco' ? readFrameData(prototipo).alto : 200;
    if (!at) {
      // Una tarjeta nueva nunca tapa a otra ni cae fuera de la vista:
      // busca un rectángulo libre y, al llegar al borde, vuelve a la esquina visible.
      const visible = {
        izquierda: screenToWorld({ x: 72, y: 72 }, cameraRef.current).x,
        arriba: screenToWorld({ x: 72, y: 72 }, cameraRef.current).y,
        derecha: screenToWorld({ x: Math.max(72, viewportSize.width - 72), y: 72 }, cameraRef.current).x,
        abajo: screenToWorld({ x: 72, y: Math.max(72, viewportSize.height - 72) }, cameraRef.current).y,
      };
      const medidas = measureCardSizes();
      const libre = (candidatoX: number, candidatoY: number) => !boardActual.cards.some((item) => {
        const medida = medidas.get(item.id);
        const anchoItem = medida?.width ?? item.width;
        const altoItem = medida?.height ?? (item.type === 'marco'
          ? readFrameData(item).alto
          : item.type === 'columna'
            ? 260
            : item.height ?? 200);
        return candidatoX < item.x + anchoItem && candidatoX + ancho > item.x
          && candidatoY < item.y + altoItem && candidatoY + alto > item.y;
      });
      // Espiral desde el centro: el primer hueco visible sin tapar nada. Si el
      // tablero está lleno, cae arriba a la izquierda, que sigue siendo visible.
      const paso = 40;
      let colocado = false;
      for (let anillo = 0; anillo <= 18 && !colocado; anillo += 1) {
        for (let ix = -anillo; ix <= anillo && !colocado; ix += 1) {
          for (let iy = -anillo; iy <= anillo && !colocado; iy += 1) {
            if (Math.abs(ix) !== anillo && Math.abs(iy) !== anillo) continue;
            const candidatoX = x + ix * paso;
            const candidatoY = y + iy * paso;
            if (candidatoX < visible.izquierda || candidatoY < visible.arriba) continue;
            if (candidatoX + ancho > visible.derecha || candidatoY + alto > visible.abajo) continue;
            if (libre(candidatoX, candidatoY)) {
              x = candidatoX;
              y = candidatoY;
              colocado = true;
            }
          }
        }
      }
      if (!colocado) {
        x = visible.izquierda + 24;
        y = visible.arriba + 24;
      }
    }
    const card = tool.crear(x, y) as BoardCard;
    configure?.(card);
    updateBoard((board) => ({ ...board, cards: [...board.cards, card] }));
    setSelectedCardIds([card.id]);
    return card;
  }, [activeBoard, frameToolId, measureCardSizes, updateBoard, viewportSize]);

  const chooseTool = useCallback((toolId: string) => {
    setAddMenuOpen(false);
    if (toolId === 'marco') {
      setFrameToolId(toolId);
      setNotice('Arrastra en la pizarra para dibujar el marco. Escape para cancelar.');
      return;
    }
    if (toolId === 'tablero') {
      setNestedDialog(true);
      return;
    }
    setFrameToolId(null);
    addToolCard(toolId);
  }, [addToolCard]);

  const activarHerramienta = (toolId: string) => {
    if (toolId === 'link') {
      setLinkDialog(true);
      setLinkError(null);
      return;
    }
    if (toolId === 'media') {
      mediaInput.current?.click();
      return;
    }
    chooseTool(toolId);
  };

  const startToolDrag = (toolId: string) => (event: React.DragEvent<HTMLButtonElement>) => {
    event.dataTransfer.setData('application/x-prometeo-tool', toolId);
    event.dataTransfer.effectAllowed = 'copy';
  };

  const dropTool = (event: React.DragEvent<HTMLDivElement>) => {
    if (!activeBoard) return;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    const archivos = Array.from(event.dataTransfer.files ?? []);
    if (archivos.length) {
      event.preventDefault();
      const punto = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
      archivos.forEach((file, indice) => {
        void addMedia(file, { x: punto.x + indice * 36, y: punto.y + indice * 28 });
      });
      return;
    }
    const toolId = event.dataTransfer.getData('application/x-prometeo-tool');
    if (!toolId) return;
    event.preventDefault();
    const punto = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
    const tool = getBoardTool(toolId);
    if (tool?.tipo === 'marco') {
      setFrameToolId(null);
      addToolCard(toolId, undefined, punto);
      setNotice('Marco creado. Arrástralo por la cabecera o cambia de vista en su menú.');
      return;
    }
    addToolCard(toolId, undefined, punto);
  };

  const publicarSeleccion = () => {
    const marcoSeleccionado = selectedCards.find((card) => card.type === 'marco');
    if (!marcoSeleccionado) {
      setNotice('Selecciona un marco para publicar su vista actual.');
      return;
    }
    void publishFrame(marcoSeleccionado);
  };


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
    detenerInercia();
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    // El gesto anula transiciones CSS de transform mientras dura; el DOM, no React.
    marcarGestoVisual(160);
    const actual = cameraRef.current;
    const delta = deltaDeRueda(event, rect.height);
    if (event.metaKey || event.ctrlKey) {
      const focal = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      // 1:1 con el delta del trackpad: sin muelle, sin lerp y sin inercia propia.
      cameraRef.current = zoomAtPoint(actual, actual.zoom * factorDePellizco(delta.y), focal);
    } else {
      cameraRef.current = { ...actual, pan: { x: actual.pan.x - delta.x, y: actual.pan.y - delta.y } };
    }
    // Se escribe en el transform en el mismo frame; rAF solo se usa para el arrastre.
    aplicarCamara();
    programarSincronizacion();
  }, [aplicarCamara, detenerInercia, marcarGestoVisual, programarSincronizacion]);

  useEffect(() => {
    wheelHandlerRef.current = handleWheel;
  }, [handleWheel]);

  // Se engancha una sola vez al viewport: cambiar de estado no deja una ventana sin rueda.
  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const alRodar = (event: WheelEvent) => wheelHandlerRef.current(event);
    element.addEventListener('wheel', alRodar, { passive: false });
    return () => element.removeEventListener('wheel', alRodar);
  }, [loaded]);

  /**
   * Safari y WKWebView no siempre entregan el pellizco como ctrl+wheel. Los eventos
   * `gesture*` se cancelan para que el WebView no haga zoom de página y se traducen
   * al mismo zoom de cámara, sin muelle y en el mismo frame.
   */
  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    let base: { zoom: number; pan: { x: number; y: number }; focal: { x: number; y: number } } | null = null;
    const start = (event: Event) => {
      const gesto = event as GestoWebKit;
      if (typeof gesto.scale !== 'number') return;
      event.preventDefault();
      detenerInercia();
      marcarGestoVisual();
      const rect = element.getBoundingClientRect();
      const focal = { x: (gesto.clientX ?? rect.left + rect.width / 2) - rect.left, y: (gesto.clientY ?? rect.top + rect.height / 2) - rect.top };
      base = { zoom: cameraRef.current.zoom, pan: cameraRef.current.pan, focal };
    };
    const change = (event: Event) => {
      const gesto = event as GestoWebKit;
      if (!base || typeof gesto.scale !== 'number') return;
      event.preventDefault();
      cameraRef.current = zoomAtPoint({ zoom: base.zoom, pan: base.pan }, base.zoom * gesto.scale, base.focal);
      aplicarCamara();
    };
    const end = (event: Event) => {
      if (!base) return;
      event.preventDefault();
      base = null;
      terminarGestoVisual();
      programarSincronizacion();
    };
    element.addEventListener('gesturestart', start, { passive: false });
    element.addEventListener('gesturechange', change, { passive: false });
    element.addEventListener('gestureend', end, { passive: false });
    return () => {
      element.removeEventListener('gesturestart', start);
      element.removeEventListener('gesturechange', change);
      element.removeEventListener('gestureend', end);
    };
  }, [aplicarCamara, detenerInercia, loaded, marcarGestoVisual, programarSincronizacion, terminarGestoVisual]);

  const zoomBy = (factor: number) => {
    const { width, height } = viewportSize;
    const camera = zoomAtPoint(cameraRef.current, cameraRef.current.zoom * factor, { x: width / 2, y: height / 2 });
    cameraRef.current = camera;
    aplicarCamara();
    sincronizarCamara();
  };

  const fitBoard = () => centerCamera(activeBoard);

  const iniciarMarquesina = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    detenerInercia();
    marcarGestoVisual();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const modo = event.altKey ? 'restar' : event.shiftKey ? 'sumar' : 'reemplazar';
    marqueeDrag.current = { pointerId: event.pointerId, startX: x, startY: y, captureEl: event.currentTarget, modo };
    setMarquee({ x, y, width: 0, height: 0 });
    setGuias({});
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  };

  const moverMarquesina = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = marqueeDrag.current;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!drag || !rect || drag.pointerId !== event.pointerId) return;
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    setMarquee({
      x: Math.min(drag.startX, x),
      y: Math.min(drag.startY, y),
      width: Math.abs(x - drag.startX),
      height: Math.abs(y - drag.startY),
    });
  };

  const terminarMarquesina = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = marqueeDrag.current;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!drag || !rect || drag.pointerId !== event.pointerId) return;
    marqueeDrag.current = null;
    liberarPuntero(drag.captureEl, event.pointerId);
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const ancho = Math.abs(x - drag.startX);
    const alto = Math.abs(y - drag.startY);
    setMarquee(null);
    if (ancho < 5 && alto < 5) return;
    const a = screenToWorld({ x: Math.min(drag.startX, x), y: Math.min(drag.startY, y) }, cameraRef.current);
    const b = screenToWorld({ x: Math.max(drag.startX, x), y: Math.max(drag.startY, y) }, cameraRef.current);
    const dentro = (activeBoard?.cards ?? []).filter((card) => {
      if (framedChildIds.has(card.id)) return false;
      const caja = rectDeTarjeta(card);
      const centroX = caja.x + caja.width / 2;
      const centroY = caja.y + caja.height / 2;
      return centroX >= a.x && centroX <= b.x && centroY >= a.y && centroY <= b.y;
    }).map((card) => card.id);
    const modo = drag.modo;
    setSelectedCardIds((current) => aplicarMarquesina(current, dentro, modo));
    suppressViewportClick.current = true;
    window.setTimeout(() => { suppressViewportClick.current = false; }, 0);
    setNotice(modo === 'reemplazar'
      ? (dentro.length
        ? `${dentro.length} ${dentro.length === 1 ? 'tarjeta seleccionada' : 'tarjetas seleccionadas'} con el rectángulo.`
        : 'El rectángulo no tocó ninguna tarjeta.')
      : modo === 'sumar'
        ? `Rectángulo sumado: ${dentro.length} ${dentro.length === 1 ? 'tarjeta más' : 'tarjetas más'}.`
        : `Rectángulo restado: ${dentro.length} ${dentro.length === 1 ? 'tarjeta' : 'tarjetas'}.`);
  };

  const beginPan = (event: React.PointerEvent<HTMLDivElement>, force = false) => {
    if (event.button !== 0 || (!force && (event.target as HTMLElement).closest('.board-card, .board-frame, .board-free-media, .board-controls, .board-dialog, button, input, select, a, .board-empty'))) return;
    detenerInercia();
    marcarGestoVisual();
    if (settleTimer.current) { window.clearTimeout(settleTimer.current); settleTimer.current = null; }
    setSettlingIds([]);
    setGuias({});
    limpiarInclinacion();
    const posicion = cameraRef.current.pan;
    panDrag.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      panX: posicion.x,
      panY: posicion.y,
      samples: [{ t: performance.now(), x: posicion.x, y: posicion.y }],
      captureEl: event.currentTarget,
    };
    setIsPanning(true);
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  };

  const movePan = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = panDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const siguiente = { x: drag.panX + event.clientX - drag.x, y: drag.panY + event.clientY - drag.y };
    cameraRef.current = { ...cameraRef.current, pan: siguiente };
    drag.samples.push({ t: performance.now(), x: siguiente.x, y: siguiente.y });
    if (drag.samples.length > 10) drag.samples.shift();
    pintarCamara();
  };

  const endPan = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = panDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const movido = Math.hypot(event.clientX - drag.x, event.clientY - drag.y) > 4;
    panDrag.current = null;
    setIsPanning(false);
    liberarPuntero(drag.captureEl, event.pointerId);
    if (movido) {
      // Un paneo no es un clic en el vacío: no debe borrar la selección actual.
      suppressViewportClick.current = true;
      window.setTimeout(() => { suppressViewportClick.current = false; }, 0);
    }
    const velocidad = velocidadDeMuestras(drag.samples, 90);
    terminarGestoVisual();
    programarSincronizacion();
    iniciarInercia(velocidad.x, velocidad.y);
  };

  const viewportWorldPoint = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
  };

  const distanciaEntreToques = (): number => {
    const puntos = [...touchPoints.current.values()];
    if (puntos.length < 2) return 0;
    return Math.hypot(puntos[1].x - puntos[0].x, puntos[1].y - puntos[0].y);
  };

  const medioDeToques = (): { x: number; y: number } => {
    const puntos = [...touchPoints.current.values()];
    if (!puntos.length) return { x: 0, y: 0 };
    const suma = puntos.reduce((total, punto) => ({ x: total.x + punto.x, y: total.y + punto.y }), { x: 0, y: 0 });
    return { x: suma.x / puntos.length, y: suma.y / puntos.length };
  };

  /** Un dedo dibuja marquesina; dos dedos panean y pellizcan hacia el punto medio. */
  const iniciarToque = (event: React.PointerEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest('.board-card, .board-column, .board-frame, .board-free-media, .board-controls, .board-dialog, button, input, select, a, .board-empty')) return;
    event.preventDefault();
    touchPoints.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* puntero sintético */ }
    if (touchIgnore.current) return;

    const cantidad = touchPoints.current.size;
    if (cantidad >= 2) {
      // El segundo dedo cancela la marquesina: dos dedos son cámara, nunca selección.
      if (marqueeDrag.current) {
        liberarPuntero(marqueeDrag.current.captureEl, marqueeDrag.current.pointerId);
        marqueeDrag.current = null;
      }
      setMarquee(null);
      detenerInercia();
      marcarGestoVisual();
      touchGesture.current = {
        mode: 'camera',
        baseCamera: { pan: { ...cameraRef.current.pan }, zoom: cameraRef.current.zoom },
        baseDist: Math.max(1, distanciaEntreToques()),
        baseMid: medioDeToques(),
      };
      return;
    }

    if (cantidad === 1) {
      if (handMode || spaceHeld.current) {
        detenerInercia();
        marcarGestoVisual();
        touchGesture.current = {
          mode: 'camera',
          baseCamera: { pan: { ...cameraRef.current.pan }, zoom: cameraRef.current.zoom },
          baseMid: { x: event.clientX, y: event.clientY },
        };
        return;
      }
      touchGesture.current = { mode: 'marquee' };
      iniciarMarquesina(event);
    }
  };

  const moverToque = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!touchPoints.current.has(event.pointerId)) return;
    touchPoints.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const gesto = touchGesture.current;
    if (!gesto) return;
    if (gesto.mode === 'marquee') {
      moverMarquesina(event);
      return;
    }
    if (!gesto.baseCamera) return;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    const cantidad = touchPoints.current.size;
    const medio = medioDeToques();
    if (cantidad >= 2 && gesto.baseDist) {
      // Paneo del punto medio + zoom focal en el mismo frame, sin inercia propia.
      const panned = {
        zoom: gesto.baseCamera.zoom,
        pan: {
          x: gesto.baseCamera.pan.x + (medio.x - (gesto.baseMid?.x ?? medio.x)),
          y: gesto.baseCamera.pan.y + (medio.y - (gesto.baseMid?.y ?? medio.y)),
        },
      };
      const escala = distanciaEntreToques() / gesto.baseDist;
      cameraRef.current = zoomAtPoint(panned, gesto.baseCamera.zoom * escala, { x: medio.x - rect.left, y: medio.y - rect.top });
    } else {
      cameraRef.current = {
        zoom: gesto.baseCamera.zoom,
        pan: {
          x: gesto.baseCamera.pan.x + (event.clientX - (gesto.baseMid?.x ?? event.clientX)),
          y: gesto.baseCamera.pan.y + (event.clientY - (gesto.baseMid?.y ?? event.clientY)),
        },
      };
    }
    aplicarCamara();
  };

  const terminarToque = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!touchPoints.current.has(event.pointerId)) return;
    touchPoints.current.delete(event.pointerId);
    const gesto = touchGesture.current;
    if (gesto?.mode === 'marquee' && marqueeDrag.current?.pointerId === event.pointerId) {
      terminarMarquesina(event);
    }
    if (touchPoints.current.size < 2 && gesto?.mode === 'camera') {
      touchGesture.current = null;
      // El dedo que queda no debe convertirse en marquesina sin levantar del todo.
      touchIgnore.current = touchPoints.current.size > 0;
      terminarGestoVisual();
      programarSincronizacion();
    }
    if (touchPoints.current.size === 0) {
      touchGesture.current = null;
      touchIgnore.current = false;
      terminarGestoVisual();
      programarSincronizacion();
    }
  };

  const startFrameDraw = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !frameToolId) return;
    if ((event.target as HTMLElement).closest('button, input, select, textarea, a, .board-free-media, .board-zoom-controls, .board-empty, .board-controls')) return;
    detenerInercia();
    marcarGestoVisual();
    const start = viewportWorldPoint(event);
    frameDraw.current = { pointerId: event.pointerId, start, captureEl: event.currentTarget };
    setFrameDraft(rectFromPoints(start, start));
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
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
    terminarGestoVisual();
    liberarPuntero(drag.captureEl, event.pointerId);
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
    if (event.pointerType === 'touch') {
      iniciarToque(event);
      return;
    }
    const target = event.target as HTMLElement;
    if (!target.closest('input, textarea, select, [contenteditable="true"]')) {
      viewportRef.current?.focus({ preventScroll: true });
    }
    if (spaceHeld.current && event.button === 0) {
      beginPan(event, true);
      return;
    }
    if (frameToolId) {
      startFrameDraw(event);
      return;
    }
    if (handMode && event.button === 0) {
      beginPan(event);
      return;
    }
    if (event.button === 0) {
      const target = event.target as HTMLElement;
      if (!target.closest('.board-card, .board-column, .board-frame, .board-free-media, .board-controls, .board-dialog, button, input, select, a, .board-empty')) {
        iniciarMarquesina(event);
        return;
      }
    }
    beginPan(event);
  };

  const moveViewportGesture = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch') {
      moverToque(event);
      return;
    }
    if (marqueeDrag.current) moverMarquesina(event);
    else if (frameDraw.current) moveFrameDraw(event);
    else movePan(event);
  };

  const endViewportGesture = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch') {
      terminarToque(event);
      return;
    }
    if (marqueeDrag.current) terminarMarquesina(event);
    else if (frameDraw.current) endFrameDraw(event);
    else endPan(event);
  };

  const startCardDrag = (card: BoardCard, event: React.PointerEvent<HTMLElement>) => {
    detenerInercia();
    if (spaceHeld.current || event.button !== 0 || event.detail > 1 || frameToolId || connectMode || card.locked || (event.target as HTMLElement).closest('input,button,a,textarea,select,.board-inline-input') || !activeBoard) return;
    marcarGestoVisual();
    suppressCardClick.current = false;
    if (settleTimer.current) { window.clearTimeout(settleTimer.current); settleTimer.current = null; }
    setSettlingIds([]);
    setGuias({});
    limpiarInclinacion();
    const hasModifier = event.shiftKey || event.metaKey || event.ctrlKey;
    let nextSelection = selectedCardIds;
    if (event.metaKey || event.ctrlKey) {
      nextSelection = alternarEnSeleccion(selectedCardIds, card.id);
      suppressCardClick.current = true;
    } else if (event.shiftKey) {
      nextSelection = alternarEnSeleccion(selectedCardIds, card.id);
      suppressCardClick.current = true;
    } else if (!hasModifier && !selectedCardIds.includes(card.id)) {
      nextSelection = [card.id];
    }
    if (nextSelection !== selectedCardIds) setSelectedCardIds(nextSelection);
    if (hasModifier && !nextSelection.includes(card.id)) return;

    const idsBrutos = hasModifier
      ? [card.id]
      : card.type === 'marco'
        ? [...new Set([...nextSelection.includes(card.id) ? nextSelection : [card.id], ...readFrameData(card).hijos])]
        : card.type === 'columna'
          ? [...new Set([...nextSelection.includes(card.id) ? nextSelection : [card.id], ...readColumnData(card).hijos])]
          : nextSelection.includes(card.id) ? nextSelection : [card.id];
    // Una tarjeta bloqueada nunca entra en un arrastre múltiple.
    const ids = idsBrutos.filter((id) => !activeBoard.cards.find((item) => item.id === id)?.locked);
    const positions = new Map(
      activeBoard.cards.filter((item) => ids.includes(item.id)).map((item) => [item.id, { x: item.x, y: item.y }]),
    );
    const sizes = measureCardSizes();
    sizes.set(card.id, {
      width: card.width,
      height: card.type === 'marco' ? readFrameData(card).alto : sizes.get(card.id)?.height ?? 200,
    });
    cardDrag.current = {
      pointerId: event.pointerId,
      boardId: activeBoard.id,
      ids,
      x: event.clientX,
      y: event.clientY,
      positions,
      sizes,
      startBoard: activeBoard,
      gesture: newBoardId('move'),
      moved: false,
      captureEl: event.currentTarget,
      lastX: event.clientX,
      lastY: event.clientY,
      lastT: performance.now(),
      altKey: event.altKey,
      duplicated: false,
    };
    setDraggingIds(ids);
    setDropFrameId(null);
    dropFrameIdRef.current = null;
  };

  const moveCardDrag = (event: React.PointerEvent<HTMLElement>) => {
    const drag = cardDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const distancia = Math.abs(event.clientX - drag.x) + Math.abs(event.clientY - drag.y);
    if (!drag.moved && distancia < 3) return;
    if (!drag.moved) {
      drag.moved = true;
      try { drag.captureEl?.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
    }
    // Alt/Opción + arrastrar: la copia nace en el primer movimiento, no al hacer clic.
    let base: BoardDocument = boards.find((board) => board.id === drag.boardId) ?? activeBoard;
    if (!base) return;
    if (drag.altKey && !drag.duplicated) {
      const dup = duplicateCards(base.cards, base.relations, drag.ids, { x: 0, y: 0 });
      const sizes = new Map<string, CardSize>();
      for (const [viejo, nuevo] of dup.idMap) {
        const medida = drag.sizes.get(viejo);
        if (medida) sizes.set(nuevo, medida);
      }
      base = {
        ...base,
        updatedAt: new Date().toISOString(),
        cards: [...base.cards, ...dup.cards],
        relations: [...base.relations, ...dup.relations],
      };
      drag.ids = dup.newIds;
      drag.positions = new Map(dup.cards.map((item) => [item.id, { x: item.x, y: item.y }]));
      drag.sizes = sizes;
      drag.duplicated = true;
      setSelectedCardIds(dup.newIds);
      setNotice(`Copia creada: ${dup.newIds.length === 1 ? '1 tarjeta' : `${dup.newIds.length} tarjetas`}.`);
    }
    let deltaX = (event.clientX - drag.x) / cameraRef.current.zoom;
    let deltaY = (event.clientY - drag.y) / cameraRef.current.zoom;
    const anchor = drag.positions.get(drag.ids[0]);
    if (snapEnabled && anchor) {
      deltaX = snapPosition(anchor.x + deltaX, GRID_SIZE) - anchor.x;
      deltaY = snapPosition(anchor.y + deltaY, GRID_SIZE) - anchor.y;
    }
    const tablero = base;
    const arrastrados = new Set(drag.ids);
    if (anchor && tablero) {
      const tamano = drag.sizes.get(drag.ids[0]) ?? { width: 260, height: 200 };
      const caja = { x: anchor.x + deltaX, y: anchor.y + deltaY, width: tamano.width, height: tamano.height };
      const otras = tablero.cards
        .filter((item) => !arrastrados.has(item.id))
        .map((item) => {
          const medida = drag.sizes.get(item.id);
          return {
            x: item.x,
            y: item.y,
            width: medida?.width ?? item.width,
            height: medida?.height ?? (item.type === 'marco' ? readFrameData(item).alto : 200),
          };
        });
      const iman = imanDeCaja(caja, otras, { umbral: 7 / Math.max(0.05, cameraRef.current.zoom), rejilla: GRID_SIZE });
      deltaX += iman.dx;
      deltaY += iman.dy;
      setGuias((actual) => actual.x === iman.guias.x && actual.y === iman.guias.y ? actual : iman.guias);
    } else {
      setGuias((actual) => actual.x === undefined && actual.y === undefined ? actual : {});
    }
    if (deltaX !== 0 || deltaY !== 0) drag.moved = true;

    const ahora = performance.now();
    const dt = Math.max(1, ahora - drag.lastT);
    const vx = ((event.clientX - drag.lastX) / dt) * 1000;
    drag.lastX = event.clientX;
    drag.lastY = event.clientY;
    drag.lastT = ahora;
    if (!movimientoReducido()) {
      viewportRef.current?.style.setProperty('--drag-tilt', `${inclinacionPorVelocidad(vx)}deg`);
    }

    updateBoard(() => ({
      ...tablero,
      cards: tablero.cards.map((item) => {
        const position = drag.positions.get(item.id);
        return position ? { ...item, x: position.x + deltaX, y: position.y + deltaY } : item;
      }),
    }), { recordHistory: false });

    const esMarcoArrastrado = drag.ids.some((id) => {
      const tipo = tablero?.cards.find((item) => item.id === id)?.type;
      return tipo === 'marco' || tipo === 'columna';
    });
    if (!tablero || esMarcoArrastrado) {
      setDropFrameId(null);
      dropFrameIdRef.current = null;
      return;
    }
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    const punto = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
    const destino = tablero.cards.find((item) => {
      if (arrastrados.has(item.id)) return false;
      if (item.type !== 'marco' && item.type !== 'columna') return false;
      const alto = item.type === 'columna'
        ? (viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${item.id}"]`)?.getBoundingClientRect().height ?? 200) / cameraRef.current.zoom
        : readFrameData(item).alto;
      return punto.x >= item.x && punto.x <= item.x + item.width && punto.y >= item.y && punto.y <= item.y + alto;
    });
    const siguienteDestino = destino?.id ?? null;
    dropFrameIdRef.current = siguienteDestino;
    setDropFrameId((actual) => actual === siguienteDestino ? actual : siguienteDestino);
  };

  const asentar = (ids: string[]) => {
    if (movimientoReducido() || !ids.length) {
      limpiarInclinacion();
      return;
    }
    setSettlingIds(ids);
    if (settleTimer.current) window.clearTimeout(settleTimer.current);
    settleTimer.current = window.setTimeout(() => {
      settleTimer.current = null;
      setSettlingIds([]);
      limpiarInclinacion();
    }, 280);
  };

  const endCardDrag = (event: React.PointerEvent<HTMLElement>) => {
    const drag = cardDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const tablero = boards.find((board) => board.id === drag.boardId) ?? activeBoard;
    const destino = dropFrameIdRef.current;
    let final = tablero;
    const arrastraContenedor = Boolean(tablero && drag.ids.some((id) => {
      const tipo = tablero.cards.find((item) => item.id === id)?.type;
      return tipo === 'marco' || tipo === 'columna';
    }));
    if (tablero && !arrastraContenedor) {
      const adoptados = new Set(drag.ids);
      final = {
        ...tablero,
        updatedAt: new Date().toISOString(),
        cards: tablero.cards.map((item) => {
          if (item.type === 'columna') {
            const datos = readColumnData(item);
            const hijos = datos.hijos.filter((id) => !adoptados.has(id));
            return destino === item.id
              ? { ...item, datos: { ...item.datos, ...datos, hijos: [...new Set([...hijos, ...drag.ids])] } }
              : { ...item, datos: { ...item.datos, ...datos, hijos } };
          }
          if (item.type !== 'marco') return item;
          const datos = readFrameData(item);
          const hijos = datos.hijos.filter((id) => !adoptados.has(id));
          return destino === item.id
            ? { ...item, datos: { ...item.datos, ...datos, hijos: [...new Set([...hijos, ...drag.ids])] } }
            : { ...item, datos: { ...item.datos, ...datos, hijos } };
        }),
      };
    }
    if (final && drag.ids.some((id) => {
      const before = drag.startBoard.cards.find((item) => item.id === id);
      const after = final.cards.find((item) => item.id === id);
      return before && after && (before.x !== after.x || before.y !== after.y);
    })) {
      setBoardHistories((current) => ({
        ...current,
        [drag.boardId]: recordBoardChange(current[drag.boardId] ?? emptyBoardHistory(), drag.startBoard, final, drag.gesture),
      }));
    }
    if (final && final !== tablero) {
      setBoards((current) => current.map((board) => board.id === final.id ? final : board));
      enqueueBoardSave(final);
    }
    if (drag.moved || destino) suppressCardClick.current = true;
    liberarPuntero(drag.captureEl, drag.pointerId);
    setDraggingIds([]);
    setDropFrameId(null);
    dropFrameIdRef.current = null;
    setGuias({});
    if (drag.moved) asentar(drag.ids);
    else limpiarInclinacion();
    cardDrag.current = null;
    terminarGestoVisual();
  };

  const startFrameResize = (card: BoardCard, event: React.PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0 || !activeBoard || card.locked) return;
    event.preventDefault();
    event.stopPropagation();
    detenerInercia();
    marcarGestoVisual();
    if (settleTimer.current) { window.clearTimeout(settleTimer.current); settleTimer.current = null; }
    const alto = readFrameData(card).alto;
    frameResize.current = {
      pointerId: event.pointerId,
      cardId: card.id,
      startX: event.clientX,
      startY: event.clientY,
      width: card.width,
      height: alto,
      startBoard: activeBoard,
      captureEl: event.currentTarget,
      elemento: viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${card.id}"]`) ?? null,
      raf: 0,
      ultimo: { width: card.width, height: alto },
    };
    setDraggingIds([card.id]);
    setSettlingIds([]);
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  };

  const moveFrameResize = (event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = frameResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const escala = cameraRef.current.zoom;
    const ancho = Math.max(FRAME_MIN_SIZE, drag.width + (event.clientX - drag.startX) / escala);
    const alto = Math.max(FRAME_MIN_SIZE, drag.height + (event.clientY - drag.startY) / escala);
    drag.ultimo = { width: Math.round(ancho * 10) / 10, height: Math.round(alto * 10) / 10 };
    // Ref + rAF: se escribe en el DOM y React solo se entera al soltar.
    if (drag.raf) return;
    drag.raf = requestAnimationFrame(() => {
      drag.raf = 0;
      if (frameResize.current !== drag) return;
      if (drag.elemento) {
        drag.elemento.style.width = `${drag.ultimo.width}px`;
        drag.elemento.style.height = `${drag.ultimo.height}px`;
      }
    });
  };

  const endFrameResize = (event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = frameResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.raf) {
      cancelAnimationFrame(drag.raf);
      drag.raf = 0;
    }
    frameResize.current = null;
    liberarPuntero(drag.captureEl, event.pointerId);
    terminarGestoVisual();
    setDraggingIds([]);
    const tablero = boards.find((board) => board.id === drag.startBoard.id) ?? activeBoard;
    const marco = tablero?.cards.find((item) => item.id === drag.cardId);
    if (!tablero || !marco) return;
    const { width, height } = drag.ultimo;
    const datos = readFrameData(marco);
    const rect: FrameRect = { x: marco.x, y: marco.y, width, height };
    const hijos = esMarcoEntropia(marco)
      ? datos.hijos
      : cardsInsideFrame(tablero.cards, rect, measureCardSizes()).filter((id) => id !== marco.id);
    const final: BoardDocument = {
      ...tablero,
      updatedAt: new Date().toISOString(),
      cards: tablero.cards.map((item) => item.id === marco.id
        ? { ...item, width, datos: { ...item.datos, ...datos, alto: height, hijos } }
        : item),
    };
    setBoardHistories((current) => ({
      ...current,
      [drag.startBoard.id]: recordBoardChange(current[drag.startBoard.id] ?? emptyBoardHistory(), drag.startBoard, final, newBoardId('resize')),
    }));
    setBoards((current) => current.map((board) => board.id === final.id ? final : board));
    enqueueBoardSave(final);
    asentar([marco.id]);
  };

  /** Redimensionar una imagen o vídeo desde cualquier esquina; Shift mantiene la proporción. */
  const startFreeResize = (card: BoardCard, corner: EsquinaMedia, event: React.PointerEvent<HTMLElement>) => {
    if (event.button !== 0 || !activeBoard) return;
    event.preventDefault();
    event.stopPropagation();
    detenerInercia();
    marcarGestoVisual();
    if (settleTimer.current) { window.clearTimeout(settleTimer.current); settleTimer.current = null; }
    const elemento = viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${card.id}"]`) ?? null;
    const alto = card.height ?? (elemento ? elemento.getBoundingClientRect().height / cameraRef.current.zoom : Math.round(card.width * 0.75));
    freeResize.current = {
      pointerId: event.pointerId,
      cardId: card.id,
      corner,
      startX: event.clientX,
      startY: event.clientY,
      x: card.x,
      y: card.y,
      width: card.width,
      height: alto,
      ratio: card.width / Math.max(1, alto),
      startBoard: activeBoard,
      captureEl: event.currentTarget,
      elemento,
      raf: 0,
      ultimo: { x: card.x, y: card.y, width: card.width, height: alto },
    };
    setSelectedCardIds([card.id]);
    setSettlingIds([]);
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  };

  const moveFreeResize = (event: React.PointerEvent<HTMLElement>) => {
    const drag = freeResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const escala = cameraRef.current.zoom;
    const dx = (event.clientX - drag.startX) / escala;
    const dy = (event.clientY - drag.startY) / escala;
    const oeste = drag.corner === 'nw' || drag.corner === 'sw';
    const norte = drag.corner === 'nw' || drag.corner === 'ne';
    const brutoAncho = oeste ? drag.width - dx : drag.width + dx;
    const brutoAlto = norte ? drag.height - dy : drag.height + dy;
    let ancho = Math.max(80, brutoAncho);
    let alto = Math.max(60, brutoAlto);
    // Shift = proporción. Sin Shift, la esquina sigue al dedo en ambos ejes.
    if (event.shiftKey) {
      const mandaAncho = Math.abs(brutoAncho - drag.width) >= Math.abs(brutoAlto - drag.height);
      if (mandaAncho) {
        ancho = Math.max(80, brutoAncho);
        alto = ancho / drag.ratio;
        if (alto < 60) { alto = 60; ancho = alto * drag.ratio; }
      } else {
        alto = Math.max(60, brutoAlto);
        ancho = alto * drag.ratio;
        if (ancho < 80) { ancho = 80; alto = ancho / drag.ratio; }
      }
    }
    const x = oeste ? drag.x + (drag.width - ancho) : drag.x;
    const y = norte ? drag.y + (drag.height - alto) : drag.y;
    drag.ultimo = {
      x: Math.round(x * 10) / 10,
      y: Math.round(y * 10) / 10,
      width: Math.round(ancho * 10) / 10,
      height: Math.round(alto * 10) / 10,
    };
    // Ref + rAF: durante el gesto solo cambia el DOM; React recibe el tamaño al soltar.
    if (drag.raf) return;
    drag.raf = requestAnimationFrame(() => {
      drag.raf = 0;
      if (freeResize.current !== drag || !drag.elemento || !drag.ultimo) return;
      const { x: left, y: top, width, height } = drag.ultimo;
      drag.elemento.style.left = `${left}px`;
      drag.elemento.style.top = `${top}px`;
      drag.elemento.style.width = `${width}px`;
      drag.elemento.style.height = `${height}px`;
    });
  };

  const endFreeResize = (event: React.PointerEvent<HTMLElement>) => {
    const drag = freeResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.raf) {
      cancelAnimationFrame(drag.raf);
      drag.raf = 0;
    }
    freeResize.current = null;
    liberarPuntero(drag.captureEl, event.pointerId);
    terminarGestoVisual();
    const tablero = boards.find((board) => board.id === drag.startBoard.id) ?? activeBoard;
    const card = tablero?.cards.find((item) => item.id === drag.cardId);
    if (!tablero || !card) return;
    const tamano = drag.ultimo;
    if (!tamano) return;
    const final: BoardDocument = {
      ...tablero,
      updatedAt: new Date().toISOString(),
      cards: tablero.cards.map((item) => item.id === drag.cardId
        ? { ...item, x: tamano.x, y: tamano.y, width: tamano.width, height: tamano.height }
        : item),
    };
    setBoardHistories((current) => ({
      ...current,
      [drag.startBoard.id]: recordBoardChange(current[drag.startBoard.id] ?? emptyBoardHistory(), drag.startBoard, final, newBoardId('resize-media')),
    }));
    setBoards((current) => current.map((board) => board.id === final.id ? final : board));
    enqueueBoardSave(final);
  };

  const ajustarAlturaNatural = useCallback((cardId: string, anchoNatural: number, altoNatural: number) => {
    if (!anchoNatural || !altoNatural) return;
    updateBoard((board) => ({
      ...board,
      cards: board.cards.map((item) => item.id === cardId && item.height === undefined
        ? { ...item, height: Math.round(item.width * (altoNatural / anchoNatural) * 10) / 10 }
        : item),
    }), { recordHistory: false });
  }, [updateBoard]);

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

  /** ⌘G · un marco nuevo alrededor de la selección, detrás de sus hijos y sin mover nada. */
  const agruparSeleccion = useCallback(() => {
    const board = activeBoardRef.current;
    if (!board) return;
    const ids = selectedCardIds.filter((id) => {
      const card = board.cards.find((item) => item.id === id);
      return Boolean(card && card.type !== 'marco' && !card.locked);
    });
    if (!ids.length) {
      setNotice('Selecciona al menos una tarjeta libre para agruparla en un marco.');
      return;
    }
    const sizes = measureCardSizes();
    const cajas = board.cards
      .filter((card) => ids.includes(card.id))
      .map((card) => rectDeTarjeta(card, sizes.get(card.id)));
    const izquierda = Math.min(...cajas.map((caja) => caja.x));
    const arriba = Math.min(...cajas.map((caja) => caja.y));
    const derecha = Math.max(...cajas.map((caja) => caja.x + caja.width));
    const abajo = Math.max(...cajas.map((caja) => caja.y + caja.height));
    const margen = 32;
    const frame = getBoardTool('marco')?.crear(izquierda - margen, arriba - margen) as BoardCard | undefined;
    if (!frame) return;
    const data = readFrameData(frame);
    const ancho = Math.max(FRAME_MIN_SIZE, derecha - izquierda + margen * 2);
    const alto = Math.max(FRAME_MIN_SIZE, abajo - arriba + margen * 2);
    const conHijos: BoardCard = {
      ...frame,
      title: 'Grupo',
      width: ancho,
      datos: { ...frame.datos, ...data, alto, hijos: ids, vista: 'libre' },
    };
    updateBoard((actual) => {
      const primero = Math.min(...ids.map((id) => actual.cards.findIndex((card) => card.id === id)));
      const indice = primero < 0 ? actual.cards.length : primero;
      return {
        ...actual,
        cards: [...actual.cards.slice(0, indice), conHijos, ...actual.cards.slice(indice)],
      };
    });
    setSelectedCardIds([conHijos.id]);
    setNotice(`Grupo creado con ${ids.length} ${ids.length === 1 ? 'tarjeta' : 'tarjetas'}.`);
  }, [measureCardSizes, selectedCardIds, updateBoard]);

  /** ⌘⇧G · quita el marco (o saca las tarjetas seleccionadas) sin tocar posiciones. */
  const desagruparSeleccion = useCallback(() => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    const seleccionadas = new Set(selectedCardIds);
    const marcos = board.cards.filter((card) => seleccionadas.has(card.id) && card.type === 'marco');
    const sueltas = board.cards.filter((card) => seleccionadas.has(card.id) && card.type !== 'marco');
    if (!marcos.length && !sueltas.length) return;
    const quitar = new Set([...marcos.map((card) => card.id), ...sueltas.map((card) => card.id)]);
    updateBoard((actual) => ({
      ...actual,
      cards: actual.cards
        .filter((card) => !marcos.some((marco) => marco.id === card.id))
        .map((card) => {
          if (card.type !== 'marco' && card.type !== 'columna') return card;
          const data = card.type === 'marco' ? readFrameData(card) : readColumnData(card);
          const hijos = data.hijos.filter((id) => !quitar.has(id));
          return hijos.length === data.hijos.length
            ? card
            : { ...card, datos: { ...card.datos, ...data, hijos } };
        }),
    }));
    setSelectedCardIds((current) => current.filter((id) => !marcos.some((marco) => marco.id === id)));
    setNotice(marcos.length
      ? `${marcos.length} ${marcos.length === 1 ? 'marco desagrupado' : 'marcos desagrupados'} sin mover ninguna tarjeta.`
      : `${sueltas.length} ${sueltas.length === 1 ? 'tarjeta liberada' : 'tarjetas liberadas'} del marco.`);
  }, [selectedCardIds, updateBoard]);

  const mostrarAviso = useCallback((texto: string, deshacer?: () => void, historial = false) => {
    if (avisoTimer.current) window.clearTimeout(avisoTimer.current);
    setAviso({ texto, deshacer, historial });
    avisoTimer.current = window.setTimeout(() => {
      avisoTimer.current = null;
      setAviso(null);
    }, 5000);
  }, []);

  useEffect(() => () => {
    if (avisoTimer.current) window.clearTimeout(avisoTimer.current);
  }, []);

  const undo = useCallback(() => {
    if (!activeBoard) return;
    const history = boardHistories[activeBoard.id] ?? emptyBoardHistory();
    const result = undoBoardChange(history, activeBoard);
    if (!result.board) return;
    setBoardHistories((current) => ({ ...current, [activeBoard.id]: result.history }));
    setBoards((current) => current.map((board) => board.id === activeBoard.id ? result.board! : board));
    setSelectedCardIds((current) => current.filter((id) => result.board!.cards.some((card) => card.id === id)));
    setAviso((current) => current?.historial ? null : current);
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
    setAviso((current) => current?.historial ? null : current);
    enqueueBoardSave(result.board!);
  }, [activeBoard, boardHistories]);

  // Un solo listener de teclado para todo el lienzo. La tabla de atajos decide
  // qué hacer; aquí solo se filtran el foco y la repetición.
  useEffect(() => {
    const setSpace = (held: boolean) => {
      spaceHeld.current = held;
      setSpacePanActive(held);
    };
    const down = (event: KeyboardEvent) => {
      if (locked) return;
      // H4 · Alt+flecha va al vecino geométrico, no mueve la tarjeta.
      if (event.altKey && !event.metaKey && !event.ctrlKey && event.key.startsWith('Arrow') && !esObjetivoDeTexto(event.target)) {
        if (document.querySelector('[role="dialog"], [role="alertdialog"]')) return;
        const tablero = activeBoardRef.current;
        if (!tablero?.cards.length) return;
        const direccion: Direccion = event.key === 'ArrowLeft' ? 'izquierda'
          : event.key === 'ArrowRight' ? 'derecha'
            : event.key === 'ArrowUp' ? 'arriba' : 'abajo';
        const enfocado = (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-card-id]')?.dataset.cardId ?? null;
        const siguiente = enfocado ? vecinoGeometrico(tablero.cards, enfocado, direccion) : tablero.cards[0].id;
        if (siguiente) {
          const elemento = viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${CSS.escape(siguiente)}"]`);
          if (elemento) {
            event.preventDefault();
            elemento.focus();
          }
        }
        return;
      }
      const atajo = atajoParaEvento(event);
      if (!atajo) return;
      if (event.repeat && !atajo.repetible) return;
      // Esc sigue cerrando diálogos aunque el foco esté en un campo; el resto no.
      if (atajo.accion !== 'cerrar' && esObjetivoDeTexto(event.target)) return;
      ejecutarAtajoRef.current(atajo, event);
    };
    const up = (event: KeyboardEvent) => {
      if (event.code !== 'Space') return;
      if (spaceHeld.current) event.preventDefault();
      setSpace(false);
    };
    const blur = () => setSpace(false);
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('blur', blur);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
      window.removeEventListener('blur', blur);
    };
  }, [locked]);

  useEffect(() => {
    if (!exportMenuOpen && !libraryMenuOpen) return;
    const cerrar = (event: PointerEvent) => {
      const target = event.target as Node;
      if (exportMenuRef.current?.contains(target) || libraryMenuRef.current?.contains(target)) return;
      setExportMenuOpen(false);
      setLibraryMenuOpen(false);
    };
    window.addEventListener('pointerdown', cerrar);
    return () => window.removeEventListener('pointerdown', cerrar);
  }, [exportMenuOpen, libraryMenuOpen]);

  const handleCardSelection = (cardId: string, event: Modificadores) => {
    if (spaceHeld.current) return;
    if (suppressCardClick.current) {
      suppressCardClick.current = false;
      return;
    }
    if (event.metaKey || event.ctrlKey) {
      setSelectedCardIds((current) => alternarEnSeleccion(current, cardId));
    } else if (event.shiftKey) {
      setSelectedCardIds((current) => alternarEnSeleccion(current, cardId));
    } else {
      setSelectedCardIds([cardId]);
    }
  };

  const crearRelacion = useCallback((from: string, to: string) => {
    if (!activeBoard || from === to) return false;
    const exists = activeBoard.relations.some((relation) => [relation.from, relation.to].sort().join(':') === [from, to].sort().join(':'));
    if (exists) {
      setNotice('Estas tarjetas ya están relacionadas.');
      return false;
    }
    updateBoard((board) => ({ ...board, relations: [...board.relations, { id: newBoardId('relation'), from, to }] }));
    setNotice('Conector creado. Doble clic sobre la curva para ponerle etiqueta.');
    return true;
  }, [activeBoard, updateBoard]);

  const iniciarConector = (card: BoardCard, event: React.PointerEvent<HTMLElement>) => {
    if (event.button !== 0 || !activeBoard) return;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    connectOrigin.current = { cardId: card.id, pointerId: event.pointerId };
    const mundo = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
    setConnectDraft({ from: card.id, x: event.clientX - rect.left, y: event.clientY - rect.top, mundo, target: null });
  };

  const conectorActivo = connectDraft !== null;
  useEffect(() => {
    if (!conectorActivo) return;
    const mover = (event: PointerEvent) => {
      const origin = connectOrigin.current;
      const rect = viewportRef.current?.getBoundingClientRect();
      if (!origin || !rect) return;
      const bajo = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('[data-card-id]');
      const target = bajo?.dataset.cardId ?? null;
      const mundo = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
      setConnectDraft({ from: origin.cardId, x: event.clientX - rect.left, y: event.clientY - rect.top, mundo, target: target === origin.cardId ? null : target });
    };
    const soltar = (event: PointerEvent) => {
      const origin = connectOrigin.current;
      if (!origin) return;
      const bajo = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('[data-card-id]');
      const target = bajo?.dataset.cardId ?? null;
      connectOrigin.current = null;
      setConnectDraft(null);
      if (target && target !== origin.cardId) crearRelacion(origin.cardId, target);
      else setNotice('Suelta el conector sobre otra tarjeta para relacionarlas.');
    };
    const cancelar = () => {
      connectOrigin.current = null;
      setConnectDraft(null);
    };
    window.addEventListener('pointermove', mover);
    window.addEventListener('pointerup', soltar);
    window.addEventListener('pointercancel', cancelar);
    return () => {
      window.removeEventListener('pointermove', mover);
      window.removeEventListener('pointerup', soltar);
      window.removeEventListener('pointercancel', cancelar);
    };
  }, [conectorActivo, crearRelacion]);

  const editarEtiquetaRelacion = (relation: BoardRelation) => {
    const valor = window.prompt('Etiqueta del conector (vacío para quitarla)', relation.label ?? '');
    if (valor === null) return;
    const label = valor.trim().slice(0, 160);
    updateBoard((board) => ({
      ...board,
      relations: board.relations.map((item) => item.id === relation.id
        ? { ...item, ...(label ? { label } : { label: undefined }) }
        : item),
    }));
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
    crearRelacion(connectFromId, cardId);
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
    try {
      await deletePdfReference(reference.id);
      void recordarBorrado({
        kind: 'reference',
        label: `Referencia a «${reference.sourceName}» · página ${reference.page}`,
        payload: { reference },
      });
      setProjectReferences((current) => current.filter((item) => item.id !== reference.id));
      mostrarAviso(`Referencia a «${reference.sourceName}» eliminada · 30 días en Archivo`, () => {
        setProjectReferences((current) => current.some((item) => item.id === reference.id) ? current : [reference, ...current]);
        void savePdfReference(reference).catch((error: unknown) => {
          setProjectError(error instanceof Error ? error.message : 'No se pudo recuperar la referencia PDF.');
        });
      });
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

  const crearTableroAnidado = (destino: BoardDocument) => {
    setNestedDialog(false);
    const creada = addToolCard('tablero', (card) => {
      card.title = destino.title || 'Tablero';
      card.datos = { boardId: destino.id, boardTitle: destino.title || 'Tablero' };
    });
    if (creada) setNotice(`Tablero «${destino.title || 'sin título'}» anidado como tarjeta.`);
  };

  const abrirPlantillas = () => {
    setTemplates(listarPlantillas(activeProject?.plantillas ?? []));
    setTemplateDialog(true);
  };

  const aplicarPlantilla = async (plantilla: Plantilla) => {
    if (!(await flushBoardWrites())) {
      setNotice('No se aplicó la plantilla porque el tablero actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    const { cards, relations, title } = materializar(plantilla.board, plantilla.nombre);
    const board: BoardDocument = {
      ...createBoard(title.slice(0, 120)),
      cards,
      relations,
    };
    if (activeProjectId) {
      try {
        await assignBoardToProject(board.id, activeProjectId);
        setProjectIdByBoardId((current) => new Map(current).set(board.id, activeProjectId));
      } catch (error) {
        setProjectError(error instanceof Error ? error.message : 'No se pudo asignar el tablero al proyecto.');
        return;
      }
    }
    setBoards((current) => [...current, board]);
    setActiveBoardId(board.id);
    setSelectedCardIds([]);
    enqueueBoardSave(board, { immediate: true });
    setTemplateDialog(false);
    setNotice(`Tablero «${board.title}» creado desde la plantilla «${plantilla.nombre}».`);
  };

  const guardarTableroComoPlantilla = async () => {
    if (!activeBoard || !activeProject) return;
    const plantilla = crearPlantilla(activeBoard);
    try {
      const plantillas = await saveProjectPlantilla(activeProject.id, plantilla);
      setProjects((current) => current.map((project) => project.id === activeProject.id ? { ...project, plantillas } : project));
      setTemplates(listarPlantillas(plantillas));
      setNotice(`«${activeBoard.title}» guardado como plantilla del proyecto «${activeProject.name}».`);
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo guardar la plantilla en el proyecto.');
    }
  };

  const borrarPlantillaGuardada = async (id: string) => {
    if (!activeProject) return;
    try {
      const plantillas = await deleteProjectPlantilla(activeProject.id, id);
      setProjects((current) => current.map((project) => project.id === activeProject.id ? { ...project, plantillas } : project));
      setTemplates(listarPlantillas(plantillas));
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo eliminar la plantilla.');
    }
  };

  const commitProjectRename = async () => {
    if (!activeProject) return;
    const name = projectDraft.trim().slice(0, 120);
    setRenamingProject(false);
    if (!name || name === activeProject.name) return;
    try {
      const updated = await renameProject(activeProject.id, name);
      setProjects((current) => current.map((project) => project.id === updated.id ? updated : project));
      setProjectError(null);
      setNotice(`Proyecto renombrado a «${updated.name}».`);
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo renombrar el proyecto.');
    }
  };

  const renameBoard = (title: string) => {
    updateBoard((board) => ({ ...board, title: title.slice(0, 120) }));
  };

  const removeCurrentBoard = async () => {
    if (!activeBoard) return;
    const board = activeBoard;
    const projectId = projectIdByBoardId.get(board.id);
    if (!(await flushBoardWrites())) {
      setNotice('No se eliminó el tablero porque tiene cambios sin guardar. Reintenta o exporta una copia.');
      return;
    }
    void recordarBorrado({
      kind: 'board',
      label: `Tablero «${board.title || 'Sin título'}»`,
      payload: { board, ...(projectId ? { projectId } : {}) },
    });
    try {
      await removeBoardFromStore(board.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo quitar el tablero guardado.');
      return;
    }
    try { await removeBoardProjectLink(board.id); } catch { /* El vínculo huérfano no borra referencias ni otros tableros. */ }
    const remaining = boards.filter((item) => item.id !== board.id);
    setProjectIdByBoardId((current) => {
      const next = new Map(current);
      next.delete(board.id);
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
    mostrarAviso(`Tablero «${board.title || 'Sin título'}» eliminado · 30 días en Archivo`, () => {
      setBoards((current) => current.some((item) => item.id === board.id) ? current : [board, ...current]);
      if (projectId) {
        setProjectIdByBoardId((current) => new Map(current).set(board.id, projectId));
        void assignBoardToProject(board.id, projectId).catch((error: unknown) => {
          setProjectError(error instanceof Error ? error.message : 'No se pudo recuperar el vínculo del tablero.');
        });
      }
      setActiveBoardId(board.id);
      setSelectedCardIds([]);
      enqueueBoardSave(board, { immediate: true });
    });
  };

  /** «Archivo» no es una papelera visible: es donde se puede recuperar lo que la memoria guardó. */
  const abrirArchivo = useCallback(async () => {
    setArchiveError(null);
    setArchiveOpen(true);
    setBorrados(await listarBorrados());
  }, []);

  const refrescarArchivo = useCallback(async () => {
    setBorrados(await listarBorrados());
  }, []);

  const restaurarEntrada = async (entry: BorradoEntry) => {
    setRestoringId(entry.id);
    setArchiveError(null);
    try {
      const tomado = await tomarBorrado(entry.id);
      if (!tomado) throw new Error('Esa entrada ya no está en la memoria de 30 días.');
      if (tomado.kind === 'board' && tomado.payload.board) {
        const board = normalizeBoard(tomado.payload.board);
        if (!board) throw new Error('El tablero guardado no se pudo leer.');
        if (tomado.payload.projectId) {
          try {
            await assignBoardToProject(board.id, tomado.payload.projectId);
            setProjectIdByBoardId((current) => new Map(current).set(board.id, tomado.payload.projectId!));
          } catch {
            /* El tablero se recupera igual aunque el proyecto ya no exista. */
          }
        }
        setBoards((current) => current.some((item) => item.id === board.id) ? current.map((item) => item.id === board.id ? board : item) : [board, ...current]);
        setActiveBoardId(board.id);
        setSelectedCardIds([]);
        enqueueBoardSave(board, { immediate: true });
        setNotice(`Tablero «${board.title || 'Sin título'}» recuperado.`);
      } else if (tomado.kind === 'reference' && tomado.payload.reference) {
        await savePdfReference(tomado.payload.reference);
        setProjectReferences((current) => current.some((item) => item.id === tomado.payload.reference!.id)
          ? current
          : [tomado.payload.reference!, ...current]);
        setNotice(`Referencia a «${tomado.payload.reference.sourceName}» recuperada.`);
      } else if (tomado.kind === 'cards' && tomado.payload.cards) {
        const { boardId, cards, relations } = tomado.payload.cards;
        updateBoardById(boardId, (board) => {
          const cardsById = new Map(cards.map((card) => [card.id, card]));
          const conMarcos = board.cards.map((item) => {
            if (item.type !== 'marco') return item;
            const data = readFrameData(item);
            const dentro = cards.filter((card) => {
              const caja = rectDeTarjeta(card);
              const centroX = caja.x + caja.width / 2;
              const centroY = caja.y + caja.height / 2;
              return centroX >= item.x && centroX <= item.x + item.width
                && centroY >= item.y && centroY <= item.y + readFrameData(item).alto;
            }).map((card) => card.id);
            if (!dentro.length) return item;
            return { ...item, datos: { ...item.datos, ...data, hijos: [...new Set([...data.hijos, ...dentro])] } };
          });
          return {
            ...board,
            cards: [...conMarcos, ...cardsById.values()],
            relations: [...board.relations, ...relations.filter((relation) => !board.relations.some((item) => item.id === relation.id))],
          };
        });
        // Las relaciones externas a las tarjetas borradas ya no existen; se conservan solo las internas.
        setNotice(`${cards.length} ${cards.length === 1 ? 'tarjeta recuperada' : 'tarjetas recuperadas'} en su tablero.`);
      } else if (tomado.kind === 'project' && tomado.payload.project) {
        setNotice(`El proyecto «${tomado.payload.project.name}» se recupera desde su menú (H7).`);
      }
      setBorrados((current) => current.filter((item) => item.id !== entry.id));
      await refrescarArchivo();
    } catch (error) {
      setArchiveError(error instanceof Error ? error.message : 'No se pudo recuperar la entrada.');
    } finally {
      setRestoringId(null);
    }
  };

  const olvidarEntrada = async (id: string) => {
    await olvidarBorrado(id);
    setBorrados((current) => current.filter((item) => item.id !== id));
  };


  const aplicarVistaPrevia = useCallback(async (cardId: string, url: string) => {
    try {
      const respuesta = await studioApi.vistaPreviaUrl(url);
      const preview = normalizarVistaPrevia(respuesta, url);
      if (!preview) {
        setNotice('El enlace se guardó, pero la página no publica título, descripción ni imagen.');
        return;
      }
      updateBoard((board) => ({
        ...board,
        cards: board.cards.map((card) => card.id === cardId
          ? {
            ...card,
            title: card.title && card.title !== card.url ? card.title : (preview.titulo || preview.sitio || card.title),
            datos: { ...card.datos, vistaPrevia: preview },
          }
          : card),
      }));
      setNotice('Vista previa añadida desde el motor local.');
    } catch {
      setNotice('El enlace se guardó. No se pudo leer la vista previa; puedes añadir una nota a mano.');
    } finally {
    }
  }, [updateBoard]);

  const saveLinkCard = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isSafeExternalUrl(linkUrl)) {
      setLinkError('Usa una dirección web completa que empiece con http:// o https://.');
      return;
    }
    if (!activeBoard) return;
    const url = linkUrl.trim();
    const created = addToolCard('link', (card) => {
      card.title = linkTitle.trim() || url;
      card.url = url;
    });
    if (!created) return;
    setLinkDialog(false);
    setLinkTitle('');
    setLinkUrl('');
    setLinkError(null);
    void aplicarVistaPrevia(created.id, url);
  };

  const addMedia = useCallback(async (file?: File, at?: { x: number; y: number }) => {
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
      const tamano = kind === 'image' || kind === 'video' ? await medirMedio(dataUrl, kind) : null;
      // addToolCard coloca desde el centro del objeto: se compensa el ancho real al soltar.
      const destino = at && tamano
        ? { x: at.x - tamano.width / 2 + 130, y: at.y - tamano.height / 2 + 90 }
        : at;
      const created = addToolCard('media', (card) => {
        card.title = media.name.replace(/\.[^.]+$/, '') || 'Recurso';
        card.media = media;
        if (tamano) {
          card.width = tamano.width;
          card.height = tamano.height;
        }
      }, destino);
      if (!created) return;
      setNotice(tamano
        ? `${kind === 'video' ? 'Vídeo' : 'Imagen'} libre añadido a resolución completa.`
        : 'Recurso añadido y guardado dentro del tablero local.');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo añadir el archivo.');
    }
  }, [activeBoard, addToolCard]);

  const addMediaRef = useRef(addMedia);
  useEffect(() => {
    addMediaRef.current = addMedia;
  }, [addMedia]);

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

  const lastArrow = useRef<{ clave: string; at: number }>({ clave: '', at: 0 });
  const lastResize = useRef<{ clave: string; at: number }>({ clave: '', at: 0 });

  /** Borra N tarjetas en un solo paso de historial y ofrece deshacer durante 5 s. */
  const deleteCards = useCallback((ids: readonly string[]) => {
    const board = activeBoardRef.current ?? activeBoard;
    if (!board || !ids.length) return 0;
    const seleccionadas = new Set(ids);
    const bloqueadas = board.cards.filter((card) => seleccionadas.has(card.id) && card.locked);
    const eliminables = board.cards
      .filter((card) => seleccionadas.has(card.id) && !card.locked)
      .map((card) => card.id);
    if (!eliminables.length) {
      setNotice('Todas las tarjetas seleccionadas están bloqueadas.');
      return 0;
    }
    updateBoard((actual) => borrarTarjetas(actual, eliminables));
    const borradas = new Set(eliminables);
    const eliminadas = board.cards.filter((card) => borradas.has(card.id));
    void recordarBorrado({
      kind: 'cards',
      label: `${eliminadas.length} ${eliminadas.length === 1 ? 'tarjeta' : 'tarjetas'} de «${board.title || 'Sin título'}»`,
      payload: {
        cards: {
          boardId: board.id,
          cards: eliminadas,
          relations: board.relations.filter((relation) => borradas.has(relation.from) || borradas.has(relation.to)),
        },
      },
    });
    setSelectedCardIds((current) => current.filter((id) => !borradas.has(id)));
    const cantidad = eliminables.length;
    const bloqueo = bloqueadas.length
      ? ` · ${bloqueadas.length} ${bloqueadas.length === 1 ? 'bloqueada se queda' : 'bloqueadas se quedan'}`
      : '';
    mostrarAviso(
      `${cantidad} ${cantidad === 1 ? 'tarjeta eliminada' : 'tarjetas eliminadas'}${bloqueo} · 30 días en Archivo`,
      undefined,
      true,
    );
    return cantidad;
  }, [activeBoard, mostrarAviso, updateBoard]);

  const removeCard = (id: string) => {
    deleteCards([id]);
  };

  const deleteSelectedCards = () => {
    deleteCards(selectedCardIds);
  };

  const copiarSeleccion = useCallback((cortar: boolean) => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    const marca = copiarTarjetas(board, selectedCardIds);
    if (!marca) return;
    try {
      void navigator.clipboard?.writeText(marca).catch(() => { /* el portapapeles interno sigue disponible */ });
    } catch {
      /* Sin permiso de portapapeles la copia interna funciona igual. */
    }
    if (cortar) deleteCards(selectedCardIds);
  }, [deleteCards, selectedCardIds]);

  const pegarSeleccion = useCallback(() => {
    const board = activeBoardRef.current;
    if (!board) return false;
    const resultado = pegarTarjetas(board);
    if (!resultado) return false;
    updateBoard(() => resultado.board);
    setSelectedCardIds(resultado.newIds);
    return true;
  }, [updateBoard]);

  const duplicarSeleccionActual = useCallback(() => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    let nuevos: string[] = [];
    updateBoard((actual) => {
      const duplicado = duplicarSeleccion(actual, selectedCardIds);
      nuevos = duplicado.newIds;
      return duplicado.board;
    });
    if (nuevos.length) setSelectedCardIds(nuevos);
  }, [selectedCardIds, updateBoard]);

  const moverSeleccion = useCallback((dx: number, dy: number) => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    const ids = tarjetasAMover(board, selectedCardIds);
    if (!ids.length) return;
    const ahora = Date.now();
    const clave = claveDeRafaga(lastArrow.current.clave, lastArrow.current.at, ahora);
    lastArrow.current = { clave, at: ahora };
    updateBoard((actual) => moverTarjetas(actual, ids, dx, dy), { coalesceKey: clave });
  }, [selectedCardIds, updateBoard]);

  /** ⌘+flechas · el mismo cambio de tamaño que un asa, sin ratón. */
  const redimensionarSeleccion = useCallback((dw: number, dh: number) => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    const ids = new Set(selectedCardIds);
    const ahora = Date.now();
    const clave = claveDeRafaga(lastResize.current.clave, lastResize.current.at, ahora);
    lastResize.current = { clave, at: ahora };
    const limitar = (valor: number, min: number, max: number) => Math.max(min, Math.min(max, valor));
    updateBoard((actual) => ({
      ...actual,
      cards: actual.cards.map((card) => {
        if (!ids.has(card.id) || card.locked) return card;
        if (card.type === 'marco') {
          const data = readFrameData(card);
          return {
            ...card,
            width: limitar(card.width + dw, FRAME_MIN_SIZE, 2400),
            datos: { ...card.datos, ...data, alto: limitar(data.alto + dh, FRAME_MIN_SIZE, 100000) },
          };
        }
        if (card.type === 'columna') return { ...card, width: limitar(card.width + dw, 210, 2400) };
        if (card.type === 'media' && (card.media?.kind === 'image' || card.media?.kind === 'video')) {
          return {
            ...card,
            width: limitar(card.width + dw, 80, 1200),
            height: limitar((card.height ?? Math.round(card.width * 0.75)) + dh, 60, 2400),
          };
        }
        // Nota y enlace: solo ancho; el alto sigue al contenido (A-1 · D4).
        return { ...card, width: limitar(card.width + dw, 210, 640) };
      }),
    }), { coalesceKey: clave });
  }, [selectedCardIds, updateBoard]);

  const ordenarSeleccion = useCallback((modo: 'adelante' | 'atras' | 'frente' | 'fondo') => {
    if (!selectedCardIds.length) return;
    updateBoard((board) => ({ ...board, cards: reordenarTarjetas(board.cards, selectedCardIds, modo) }));
  }, [selectedCardIds, updateBoard]);

  /** Esc cierra primero lo que esté abierto; si no hay nada, deselecciona. */
  const cerrarAlgo = (event: KeyboardEvent): boolean => {
    if (indexOpen) {
      event.preventDefault();
      cerrarIndice(true);
      return true;
    }
    if (shortcutsOpen) {
      event.preventDefault();
      setShortcutsOpen(false);
      return true;
    }
    if (templateDialog) {
      event.preventDefault();
      setTemplateDialog(false);
      return true;
    }
    if (nestedDialog) {
      event.preventDefault();
      setNestedDialog(false);
      return true;
    }
    if (linkDialog) {
      event.preventDefault();
      setLinkDialog(false);
      return true;
    }
    if (projectDialog) {
      event.preventDefault();
      setProjectDialog(false);
      return true;
    }
    if (pdfReferenceDialog) {
      event.preventDefault();
      setPdfReferenceDialog(false);
      return true;
    }
    if (referencesOpen) {
      event.preventDefault();
      setReferencesOpen(false);
      return true;
    }
    if (mirarOpen) {
      event.preventDefault();
      setMirarOpen(false);
      return true;
    }
    if (archiveFullscreenId) {
      event.preventDefault();
      setArchiveFullscreenId(null);
      return true;
    }
    if (exportMenuOpen) {
      event.preventDefault();
      setExportMenuOpen(false);
      return true;
    }
    if (libraryMenuOpen) {
      event.preventDefault();
      setLibraryMenuOpen(false);
      return true;
    }
    if (frameToolId) {
      event.preventDefault();
      frameDraw.current = null;
      setFrameDraft(null);
      setFrameToolId(null);
      setNotice(null);
      return true;
    }
    if (addMenuOpen) {
      event.preventDefault();
      setAddMenuOpen(false);
      return true;
    }
    const enfocado = document.activeElement as HTMLElement | null;
    if (enfocado?.closest('[data-card-id]') && !enfocado.closest('input, textarea, select')) {
      event.preventDefault();
      enfocado.blur();
      viewportRef.current?.focus({ preventScroll: true });
      return true;
    }
    if (selectedCardIds.length) {
      event.preventDefault();
      setSelectedCardIds([]);
      return true;
    }
    return false;
  };

  /** Despachador único: la tabla ya decidió la acción; aquí solo se ejecuta. */
  const ejecutarAtajo = (atajo: AtajoLienzo, event: KeyboardEvent) => {
    if (shortcutsOpen && atajo.accion !== 'cerrar' && atajo.accion !== 'ayuda') return;

    if (atajo.accion === 'cerrar') {
      cerrarAlgo(event);
      return;
    }
    if (atajo.accion === 'ayuda') {
      event.preventDefault();
      setShortcutsOpen((open) => !open);
      setAddMenuOpen(false);
      return;
    }
    if (atajo.accion === 'pan') {
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('button, a, [role="button"], [role="menuitem"], [role="option"], [role="tab"]')) return;
      event.preventDefault();
      spaceHeld.current = true;
      setSpacePanActive(true);
      return;
    }
    if (atajo.accion === 'herramientas') {
      if (archiveFullscreenId) return;
      event.preventDefault();
      setAddMenuOpen((open) => !open);
      return;
    }
    if (atajo.accion === 'buscar') {
      event.preventDefault();
      searchInputRef.current?.focus();
      searchInputRef.current?.select();
      return;
    }
    if (atajo.accion === 'indice') {
      event.preventDefault();
      if (indexOpen) cerrarIndice(true);
      else abrirIndice();
      return;
    }
    if (atajo.accion === 'deshacer') {
      event.preventDefault();
      undo();
      return;
    }
    if (atajo.accion === 'rehacer') {
      event.preventDefault();
      redo();
      return;
    }
    if (atajo.accion === 'seleccionarTodo') {
      event.preventDefault();
      setSelectedCardIds(seleccionarTodoElTablero(activeBoardRef.current ?? activeBoard!, framedChildIds));
      return;
    }
    if (atajo.accion === 'pegar') {
      // El evento paste decide: imagen o texto del sistema primero, copia interna después.
      return;
    }
    if (atajo.accion === 'copiar' || atajo.accion === 'cortar') {
      if (!selectedCardIds.length) return;
      event.preventDefault();
      copiarSeleccion(atajo.accion === 'cortar');
      return;
    }
    if (!selectedCardIds.length) return;
    event.preventDefault();
    switch (atajo.accion) {
      case 'borrar':
        deleteCards(selectedCardIds);
        break;
      case 'duplicar':
        duplicarSeleccionActual();
        break;
      case 'agrupar':
        agruparSeleccion();
        break;
      case 'desagrupar':
        desagruparSeleccion();
        break;
      case 'moverIzquierda':
        moverSeleccion(-1, 0);
        break;
      case 'moverDerecha':
        moverSeleccion(1, 0);
        break;
      case 'moverArriba':
        moverSeleccion(0, -1);
        break;
      case 'moverAbajo':
        moverSeleccion(0, 1);
        break;
      case 'moverIzquierda10':
        moverSeleccion(-10, 0);
        break;
      case 'moverDerecha10':
        moverSeleccion(10, 0);
        break;
      case 'moverArriba10':
        moverSeleccion(0, -10);
        break;
      case 'moverAbajo10':
        moverSeleccion(0, 10);
        break;
      case 'redimensionarAnchoMenos':
        redimensionarSeleccion(-10, 0);
        break;
      case 'redimensionarAnchoMas':
        redimensionarSeleccion(10, 0);
        break;
      case 'redimensionarAltoMenos':
        redimensionarSeleccion(0, -10);
        break;
      case 'redimensionarAltoMas':
        redimensionarSeleccion(0, 10);
        break;
      case 'traerAdelante':
        ordenarSeleccion('adelante');
        break;
      case 'enviarAtras':
        ordenarSeleccion('atras');
        break;
      case 'alFrente':
        ordenarSeleccion('frente');
        break;
      case 'alFondo':
        ordenarSeleccion('fondo');
        break;
      default:
        break;
    }
  };
  ejecutarAtajoRef.current = ejecutarAtajo;

  /**
   * Pegar una URL de imagen sobre un Referente (o con uno seleccionado) añade un
   * medio que apunta a esa fuente con la fecha del día. No descarga la imagen.
   */
  useEffect(() => {
    const handlePaste = (event: ClipboardEvent) => {
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('input, textarea, select, [contenteditable="true"]')) return;
      const archivos = Array.from(event.clipboardData?.files ?? []).filter((file) => file.type.startsWith('image/') || file.type.startsWith('video/'));
      if (!archivos.length) {
        for (const item of Array.from(event.clipboardData?.items ?? [])) {
          if (item.kind !== 'file') continue;
          const file = item.getAsFile();
          if (file && (file.type.startsWith('image/') || file.type.startsWith('video/'))) archivos.push(file);
        }
      }
      if (archivos.length && activeBoard) {
        event.preventDefault();
        const rect = viewportRef.current?.getBoundingClientRect();
        const punto = rect
          ? screenToWorld({ x: rect.width / 2, y: rect.height / 2 }, cameraRef.current)
          : { x: 0, y: 0 };
        archivos.forEach((file, indice) => {
          void addMediaRef.current(file, { x: punto.x + indice * 36, y: punto.y + indice * 28 });
        });
        return;
      }
      const text = event.clipboardData?.getData('text/plain').trim() ?? '';
      // Copia interna: una marca corta; si el sistema trae texto o imagen, mandan ellos.
      if ((esMarcaDeTarjetas(text) || (!text && hayTarjetasCopiadas())) && pegarSeleccion()) {
        event.preventDefault();
        return;
      }
      if (!text || !isSafeExternalUrl(text) || !activeBoard) return;
      const selectedId = selectedCardIds.length === 1 ? selectedCardIds[0] : null;
      const targetId = hoveredReferenteId.current ?? selectedId;
      const card = targetId ? activeBoard.cards.find((item) => item.id === targetId && item.type === 'referente') : undefined;
      if (card) {
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
        return;
      }
      // Sin referente debajo: la URL pegada se convierte en tarjeta de enlace con
      // vista previa pedida al backend local (las claves nunca viven en el frontend).
      event.preventDefault();
      const creada = addToolCard('link', (nueva) => {
        nueva.url = text;
        nueva.title = text;
      });
      if (!creada) return;
      setNotice('Enlace pegado. Buscando título, descripción e imagen…');
      void aplicarVistaPrevia(creada.id, text);
    };
    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, [activeBoard, addToolCard, aplicarVistaPrevia, pegarSeleccion, replaceCard, selectedCardIds]);

  const onCardSelect = useCallback((card: BoardCard, event: Modificadores) => cardHandlers.current?.select(card.id, event), []);
  const onCardConnect = useCallback((cardId: string) => cardHandlers.current?.connect(cardId), []);
  const onCardConnectStart = useCallback((card: BoardCard, event: React.PointerEvent<HTMLElement>) => cardHandlers.current?.connectStart(card, event), []);
  const onCardDragStart = useCallback((card: BoardCard, event: React.PointerEvent<HTMLElement>) => cardHandlers.current?.dragStart(card, event), []);
  const onCardDragMove = useCallback((event: React.PointerEvent<HTMLElement>) => cardHandlers.current?.dragMove(event), []);
  const onCardDragEnd = useCallback((event: React.PointerEvent<HTMLElement>) => cardHandlers.current?.dragEnd(event), []);
  const onCardDelete = useCallback((cardId: string) => cardHandlers.current?.delete(cardId), []);
  const onCardPatch = useCallback((cardId: string, patch: Partial<BoardCard>) => cardHandlers.current?.patch(cardId, patch), []);
  const onCardReplace = useCallback((card: BoardCard) => cardHandlers.current?.replace(card), []);
  const onCardHover = useCallback((cardId: string, over: boolean) => cardHandlers.current?.hover(cardId, over), []);
  const onCardBlur = useCallback(() => cardHandlers.current?.blur(), []);

  cardHandlers.current = {
    select: handleCardSelection,
    connect: handleConnectCard,
    connectStart: iniciarConector,
    dragStart: startCardDrag,
    dragMove: moveCardDrag,
    dragEnd: endCardDrag,
    delete: removeCard,
    patch: updateCard,
    replace: replaceCard,
    hover: (cardId, over) => {
      if (over) hoveredReferenteId.current = cardId;
      else if (hoveredReferenteId.current === cardId) hoveredReferenteId.current = null;
    },
    blur: closeTextGroup,
  };

  const matchingCards = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return new Set((activeBoard?.cards ?? []).filter((card) => !query || `${card.title} ${card.body} ${card.url ?? ''}`.toLocaleLowerCase().includes(query)).map((card) => card.id));
  }, [activeBoard?.cards, search]);

  const resultadosBusqueda = useMemo(() => {
    const query = search.trim();
    if (!query) return [] as Array<{ boardId: string; boardTitle: string; card: BoardCard }>;
    const fuentes = searchScope === 'tablero'
      ? (activeBoard ? [activeBoard] : [])
      : projectBoards.length ? projectBoards : activeBoard ? [activeBoard] : [];
    const vistos = new Set<string>();
    const resultados: Array<{ boardId: string; boardTitle: string; card: BoardCard }> = [];
    for (const board of fuentes) {
      for (const card of board.cards) {
        if (searchScope === 'biblioteca' && !(card.type === 'referente' || board.title.toLocaleLowerCase().includes('biblioteca'))) continue;
        if (!coincideBusqueda(card, query)) continue;
        const clave = `${board.id}:${card.id}`;
        if (vistos.has(clave)) continue;
        vistos.add(clave);
        resultados.push({ boardId: board.id, boardTitle: board.title, card });
        if (resultados.length >= 200) return resultados;
      }
    }
    return resultados;
  }, [activeBoard, projectBoards, search, searchScope]);

  useEffect(() => {
    setSearchActivo(0);
  }, [search, searchScope]);

  const indiceOrdenado = useMemo(() => ordenDePintado(activeBoard?.cards ?? []), [activeBoard?.cards]);
  const indiceFiltrado = useMemo(
    () => indiceOrdenado.filter((card) => coincideBusqueda(card, indexQuery)),
    [indiceOrdenado, indexQuery],
  );
  const ventanaIndice = ventanaVirtual(indiceFiltrado.length, indexScroll, 420, INDICE_ROW_HEIGHT);
  const indiceVisibles = indiceFiltrado.slice(ventanaIndice.inicio, ventanaIndice.fin);

  useEffect(() => {
    if (!indexOpen) return;
    const frame = requestAnimationFrame(() => indexSearchRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [indexOpen]);

  const cerrarIndice = useCallback((devolverFoco = true) => {
    setIndexOpen(false);
    setIndexQuery('');
    setIndexScroll(0);
    if (devolverFoco) viewportRef.current?.focus({ preventScroll: true });
  }, []);

  const abrirIndice = useCallback(() => {
    setIndexOpen(true);
    setIndexQuery('');
    setIndexScroll(0);
  }, []);

  /** ⌘F · Enter lleva al resultado: cambia de tablero si hace falta, selecciona y centra. */
  const centrarEnTarjeta = useCallback((boardId: string, cardId: string) => {
    const board = boardsRef.current.find((item) => item.id === boardId);
    if (!board) return;
    if (activeBoard?.id !== boardId) {
      pendingCentro.current = { boardId, cardId };
      setActiveBoardId(boardId);
      setSelectedCardIds([]);
      setSearch('');
      return;
    }
    const card = board.cards.find((item) => item.id === cardId);
    if (!card) return;
    const contenedor = board.cards.find((item) => {
      if (item.type !== 'marco') return false;
      const data = readFrameData(item);
      return data.vista !== 'libre' && data.hijos.includes(card.id);
    });
    const objetivo = contenedor ?? card;
    const medida = measureCardSizes().get(objetivo.id);
    const ancho = medida?.width ?? objetivo.width;
    const alto = medida?.height ?? objetivo.height ?? (objetivo.type === 'marco' ? readFrameData(objetivo).alto : 210);
    const zoom = Math.max(0.55, Math.min(1.4, cameraRef.current.zoom));
    cameraRef.current = {
      zoom,
      pan: {
        x: viewportSize.width / 2 - (objetivo.x + ancho / 2) * zoom,
        y: viewportSize.height / 2 - (objetivo.y + alto / 2) * zoom,
      },
    };
    setSelectedCardIds([objetivo.id]);
    setSearch('');
    aplicarCamara();
    sincronizarCamara();
    viewportRef.current?.focus({ preventScroll: true });
  }, [activeBoard?.id, aplicarCamara, measureCardSizes, sincronizarCamara, viewportSize.height, viewportSize.width]);

  useEffect(() => {
    const pendiente = pendingCentro.current;
    if (!pendiente || !activeBoard || activeBoard.id !== pendiente.boardId) return;
    pendingCentro.current = null;
    const timer = window.setTimeout(() => centrarEnTarjeta(pendiente.boardId, pendiente.cardId), 80);
    return () => window.clearTimeout(timer);
  }, [activeBoard, centrarEnTarjeta]);

  const seleccionarDesdeIndice = (card: BoardCard, event: React.MouseEvent) => {
    if (event.shiftKey || event.metaKey || event.ctrlKey) {
      setSelectedCardIds((current) => alternarEnSeleccion(current, card.id));
    } else {
      setSelectedCardIds([card.id]);
    }
  };

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
        <button className="board-back" onClick={() => void leaveBoard()} title="Volver al espacio PDF" aria-label="Volver a PDF Studio">
          <ArrowLeft size={16} aria-hidden="true" />
        </button>
        <div className="board-identity">
          <span className="board-mark" aria-hidden="true">P</span>
          {renamingProject && activeProject ? (
            <input
              className="board-project-rename"
              value={projectDraft}
              autoFocus
              maxLength={120}
              aria-label="Nombre del proyecto"
              onChange={(event) => setProjectDraft(event.target.value)}
              onBlur={() => { void commitProjectRename(); }}
              onKeyDown={(event) => {
                event.stopPropagation();
                if (event.key === 'Enter') {
                  event.preventDefault();
                  event.currentTarget.blur();
                } else if (event.key === 'Escape') {
                  event.preventDefault();
                  setProjectDraft(activeProject.name);
                  setRenamingProject(false);
                }
              }}
            />
          ) : (
            <>
              <label className="sr-only" htmlFor="project-select">Proyecto</label>
              <select
                id="project-select"
                className="board-project-select"
                value={activeProjectId}
                onChange={(event) => { void handleProjectSelect(event.target.value); }}
                onDoubleClick={(event) => {
                  if (!activeProject) return;
                  event.preventDefault();
                  setProjectDraft(activeProject.name);
                  setRenamingProject(true);
                }}
                aria-label="Elegir proyecto"
                title="Doble clic para renombrar el proyecto"
                disabled={!projects.length}
              >
                {projects.length ? projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>) : <option value="">Proyectos no disponibles</option>}
              </select>
            </>
          )}
          <span className="board-identity-separator" aria-hidden="true">·</span>
          <label className="sr-only" htmlFor="board-select">Tablero</label>
          <select id="board-select" className="board-board-select" value={activeBoard.id} onChange={(event) => {
            // El select es controlado: hay que guardar el destino antes del await,
            // porque mientras se guarda vuelve a pintar el tablero actual.
            const destino = event.target.value;
            void (async () => {
              const saved = await flushBoardWrites();
              if (!saved) {
                setNotice('No se cambió de tablero porque el actual aún no se pudo guardar. Reintenta o exporta una copia.');
                return;
              }
              setActiveBoardId(destino);
              setSelectedCardIds([]);
            })();
          }} aria-label="Elegir tablero">
            {projectBoards.map((board) => <option key={board.id} value={board.id}>{board.title || 'Sin título'}</option>)}
          </select>
          <label className="sr-only" htmlFor="design-system-select">Sistema de diseño del tablero</label>
          <select
            id="design-system-select"
            className="board-system-select"
            value={normalizeDesignSystem(activeBoard.sistema)}
            onChange={(event) => {
              const sistema = normalizeDesignSystem(event.target.value) as DesignSystemId;
              updateBoard((board) => ({ ...board, sistema }));
            }}
            aria-label="Sistema de diseño del tablero"
            title="Sistema de diseño de este tablero"
          >
            {DESIGN_SYSTEMS.map((entry) => <option key={entry.id} value={entry.id}>{entry.nombre}</option>)}
          </select>
          <button className="board-icon-button" onClick={() => { const nombre = window.prompt('Nombre del tablero', activeBoard.title); if (nombre !== null) renameBoard(nombre.trim() || activeBoard.title); }} aria-label="Renombrar tablero" title="Renombrar tablero"><Pencil size={15} /></button>
          <button className="board-icon-button" onClick={() => { setProjectName(''); setProjectDialog(true); }} aria-label="Crear proyecto" title="Crear proyecto"><FolderPlus size={16} /></button>
          <button className="board-icon-button" onClick={() => void addNewBoard()} aria-label="Crear tablero" title="Crear tablero"><Plus size={16} /></button>
          <button className="board-icon-button" onClick={abrirPlantillas} aria-label="Plantillas de tablero" title="Crear un tablero desde una plantilla"><LayoutTemplate size={15} /></button>
          <button className="board-icon-button" onClick={() => importInput.current?.click()} aria-label="Importar tablero" title="Importar tablero desde JSON o Markdown"><Upload size={15} /></button>
          <button className="board-icon-button danger" onClick={() => void removeCurrentBoard()} aria-label="Eliminar tablero" title="Eliminar tablero"><Trash2 size={15} /></button>
          <span className={`board-save-state ${saveState}`} aria-live="polite">
            {saveState === 'saving' ? 'Guardando…' : saveState === 'error' ? 'Sin guardar' : 'Guardado'}
          </span>
        </div>

        <div className="board-topbar-search">
          <Search size={14} aria-hidden="true" />
          <input
            ref={searchInputRef}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'ArrowDown') {
                event.preventDefault();
                setSearchActivo((actual) => Math.min(Math.max(0, resultadosBusqueda.length - 1), actual + 1));
              } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                setSearchActivo((actual) => Math.max(0, actual - 1));
              } else if (event.key === 'Enter') {
                const resultado = resultadosBusqueda[searchActivo] ?? resultadosBusqueda[0];
                if (resultado) {
                  event.preventDefault();
                  centrarEnTarjeta(resultado.boardId, resultado.card.id);
                }
              } else if (event.key === 'Escape') {
                event.preventDefault();
                event.stopPropagation();
                setSearch('');
                viewportRef.current?.focus({ preventScroll: true });
              }
            }}
            placeholder="Buscar en el tablero"
            aria-label="Buscar tarjetas"
            aria-expanded={Boolean(search.trim())}
          />
          {search && <button type="button" onClick={() => setSearch('')} aria-label="Limpiar búsqueda"><X size={13} /></button>}
          {search.trim() && (
            <div className="board-search-results" role="listbox" aria-label="Resultados de búsqueda">
              <div className="board-search-results-head">
                <strong aria-live="polite" data-testid="search-count">{resultadosBusqueda.length} {resultadosBusqueda.length === 1 ? 'resultado' : 'resultados'}</strong>
                <label>
                  Alcance
                  <select value={searchScope} onChange={(event) => setSearchScope(event.target.value as 'tablero' | 'proyecto' | 'biblioteca')} aria-label="Alcance de búsqueda">
                    <option value="tablero">Tablero</option>
                    <option value="proyecto">Proyecto</option>
                    <option value="biblioteca">Biblioteca</option>
                  </select>
                </label>
              </div>
              {resultadosBusqueda.length === 0 ? (
                <p className="board-search-empty">Nada coincide. Prueba otro término o alcance.</p>
              ) : (
                <ul>
                  {resultadosBusqueda.slice(0, 40).map((resultado, indice) => (
                    <li key={`${resultado.boardId}:${resultado.card.id}`}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={indice === searchActivo}
                        className={indice === searchActivo ? 'is-active' : ''}
                        onMouseEnter={() => setSearchActivo(indice)}
                        onClick={() => centrarEnTarjeta(resultado.boardId, resultado.card.id)}
                      >
                        <span className="board-search-result-title">{resultado.card.title || 'Sin título'}</span>
                        <span className="board-search-result-meta">{resultado.card.type} · {resultado.boardTitle}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <p className="board-search-hint">Enter salta al primero · ↑↓ recorre · Esc vuelve al lienzo</p>
            </div>
          )}
        </div>

        <div className="board-topbar-actions">
          <button className="board-icon-button" onClick={undo} disabled={!canUndo} title="Deshacer (⌘/Ctrl + Z)" aria-label="Deshacer"><Undo2 size={16} /></button>
          <button className="board-icon-button" onClick={redo} disabled={!canRedo} title="Rehacer (⌘/Ctrl + Shift + Z)" aria-label="Rehacer"><Redo2 size={16} /></button>
          <span className="board-tool-divider" aria-hidden="true" />
          <button
            type="button"
            className={`board-icon-button ${handMode ? 'active' : ''}`}
            onClick={() => setHandMode((value) => !value)}
            aria-pressed={handMode}
            aria-label={handMode ? 'Mano activa: mover el lienzo' : 'Mano: mover el lienzo con un dedo'}
            title={handMode ? 'Mano activa · un dedo mueve el lienzo' : 'Mano · un dedo mueve el lienzo'}
          ><Hand size={16} /></button>
          <button className={`board-icon-button ${connectMode ? 'active' : ''}`} onClick={() => { setConnectMode((value) => !value); setConnectFromId(null); setNotice(connectMode ? null : 'Elige una tarjeta y luego otra para conectarlas.'); }} aria-pressed={connectMode} title="Relacionar tarjetas" aria-label="Relacionar tarjetas"><Link2 size={16} /></button>
          <button className={`board-icon-button ${snapEnabled ? 'active' : ''}`} onClick={() => setSnapEnabled((enabled) => !enabled)} aria-pressed={snapEnabled} title="Ajustar a la cuadrícula" aria-label="Ajustar a la cuadrícula"><Magnet size={16} /></button>
          <span className="board-tool-divider" aria-hidden="true" />
          <button className="board-icon-button" onClick={() => zoomBy(1 / 1.15)} aria-label="Alejar" title="Alejar"><ZoomOut size={16} /></button>
          <button ref={zoomValueRef} className="board-zoom-value" onClick={fitBoard} title="Ajustar el tablero a la pantalla" aria-label={`Zoom ${Math.round(zoom * 100)} por ciento, ajustar tablero`}>{Math.round(zoom * 100)}%</button>
          <button className="board-icon-button" onClick={() => zoomBy(1.15)} aria-label="Acercar" title="Acercar"><ZoomIn size={16} /></button>

          <button
            type="button"
            className="board-icon-button board-help-button"
            onClick={() => setShortcutsOpen(true)}
            aria-label="Atajos de teclado"
            title="Atajos de teclado (?)"
          >?</button>

          <div className="board-menu-wrap" ref={exportMenuRef}>
            <button type="button" className="board-bar-button" onClick={() => { setExportMenuOpen((open) => !open); setLibraryMenuOpen(false); }} aria-haspopup="menu" aria-expanded={exportMenuOpen} title="Exportar y publicar">
              <Download size={15} /> Exportar <ChevronDown size={14} />
            </button>
            {exportMenuOpen && (
              <div className="board-menu" role="menu" aria-label="Exportar">
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportJson(); }}>JSON del tablero</button>
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportMarkdown(); }}>Markdown</button>
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportProjectMarkdown(); }} disabled={!activeProject}>Obsidian del proyecto</button>
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportReferentesObsidian(); }}>Referentes a Obsidian</button>
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); publicarSeleccion(); }}>Publicar marco seleccionado</button>
              </div>
            )}
          </div>

          <div className="board-menu-wrap" ref={libraryMenuRef}>
            <button type="button" className="board-bar-button" onClick={() => { setLibraryMenuOpen((open) => !open); setExportMenuOpen(false); }} aria-haspopup="menu" aria-expanded={libraryMenuOpen} title="Biblioteca y rituales">
              <Library size={15} /> Biblioteca <ChevronDown size={14} />
            </button>
            {libraryMenuOpen && (
              <div className="board-menu" role="menu" aria-label="Biblioteca">
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); setMirarOpen(true); }}>Volver a mirar</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); void crearManifiesto(); }} disabled={manifesting}>{manifesting ? 'Escribiendo…' : 'Manifiesto de la semana'}</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); void importReferentes(); }}>Importar referentes</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); gustosInput.current?.click(); }}>Importar gustos</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); setPdfReferenceDialog(true); }} disabled={!activeProject || !pdfReferenceSource}>Referenciar página PDF</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); setReferencesOpen(true); }} disabled={!activeProjectReferences.length}>Referencias PDF ({activeProjectReferences.length})</button>
              </div>
            )}
          </div>

          <button
            type="button"
            className="board-icon-button"
            onClick={() => (indexOpen ? cerrarIndice(true) : abrirIndice())}
            aria-label="Índice del tablero"
            title="Índice del tablero (L)"
          ><List size={16} /></button>
          <button
            type="button"
            className="board-icon-button"
            onClick={() => void abrirArchivo()}
            aria-label="Archivo y recientes borrados"
            title="Archivo · recientes borrados (30 días)"
          ><Archive size={16} /></button>
        </div>
      </header>

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
      {aviso && (
        <div className="board-toast board-undo-toast" role="status" data-testid="board-undo-toast">
          <span>{aviso.texto}</span>
          {(aviso.historial || aviso.deshacer) && (
            <button
              type="button"
              className="board-undo-action"
              onClick={() => {
                const deshacer = aviso.historial ? undo : aviso.deshacer;
                setAviso(null);
                deshacer?.();
              }}
            >Deshacer</button>
          )}
          <button type="button" onClick={() => setAviso(null)} aria-label="Cerrar aviso"><X size={14} /></button>
        </div>
      )}
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

      {indexOpen && activeBoard && (
        <aside className="board-index-panel" aria-label="Índice del tablero">
          <div className="board-index-head">
            <div>
              <strong>Índice</strong>
              <span>{indiceFiltrado.length} de {activeBoard.cards.length} · arriba se pinta encima</span>
            </div>
            <button type="button" className="board-icon-button" onClick={() => cerrarIndice(true)} aria-label="Cerrar índice"><X size={15} /></button>
          </div>
          <input
            ref={indexSearchRef}
            className="board-index-search"
            value={indexQuery}
            onChange={(event) => { setIndexQuery(event.target.value); setIndexScroll(0); }}
            placeholder="Buscar en el índice"
            aria-label="Buscar en el índice"
          />
          <div className="board-index-tools">
            <span aria-live="polite">{selectedCardIds.length} {selectedCardIds.length === 1 ? 'seleccionada' : 'seleccionadas'}</span>
            <button type="button" className="board-tool" onClick={() => ordenarSeleccion('frente')} disabled={!selectedCardIds.length}>Traer al frente</button>
          </div>
          <div
            className="board-index-list"
            style={{ height: 420 }}
            onScroll={(event) => setIndexScroll(event.currentTarget.scrollTop)}
            role="listbox"
            aria-label="Tarjetas en orden de pintado"
            aria-multiselectable="true"
          >
            <div style={{ paddingTop: ventanaIndice.offsetSuperior, paddingBottom: ventanaIndice.offsetInferior }}>
              {indiceVisibles.map((card) => (
                <div
                  key={card.id}
                  className={`board-index-row ${selectedCardIds.includes(card.id) ? 'selected' : ''}`}
                  style={{ height: INDICE_ROW_HEIGHT }}
                  role="option"
                  aria-selected={selectedCardIds.includes(card.id)}
                  tabIndex={0}
                  onClick={(event) => seleccionarDesdeIndice(card, event)}
                  onKeyDown={(event) => {
                    if (event.target !== event.currentTarget) return;
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      seleccionarDesdeIndice(card, event as unknown as React.MouseEvent);
                    }
                  }}
                >
                  <span className="board-index-title">{card.title || 'Sin título'}</span>
                  <span className="board-index-meta">{card.type}{card.locked ? ' · bloqueada' : ''}</span>
                  <button
                    type="button"
                    className="board-index-lock"
                    onPointerDown={(event) => event.stopPropagation()}
                    onClick={(event) => { event.stopPropagation(); updateCard(card.id, { locked: !card.locked }); }}
                    aria-label={card.locked ? `Desbloquear ${card.title || 'tarjeta'}` : `Bloquear ${card.title || 'tarjeta'}`}
                  >{card.locked ? <Lock size={13} /> : <LockOpen size={13} />}</button>
                </div>
              ))}
            </div>
          </div>
          <p className="board-index-foot">El índice es una lista, no un panel de capas: se abre con L y Esc vuelve al lienzo.</p>
        </aside>
      )}

      <div className="board-body">
        <aside className="board-rail" aria-label="Herramientas del tablero">
          {RAIL_TOOLS.map((toolId) => {
            const tool = getBoardTool(toolId);
            if (!tool) return null;
            const Icono = tool.icono;
            const etiquetas: Record<string, string> = { note: 'Nota', link: 'Enlace', media: 'Imagen', tareas: 'Tareas', columna: 'Columna', referente: 'Referente', marco: 'Marco', entropia: 'Entropía' };
            const aria: Record<string, string> = { note: 'Nueva nota', link: 'Añadir enlace', media: 'Añadir imagen', tareas: 'Nueva lista de tareas', columna: 'Nueva columna', referente: 'Añadir referente', marco: 'Dibujar marco', entropia: 'Añadir entropía' };
            return (
              <button
                key={toolId}
                type="button"
                className={`board-rail-tool ${toolId === 'note' ? 'primary' : ''} ${frameToolId === toolId ? 'active' : ''}`}
                onClick={() => activarHerramienta(toolId)}
                draggable
                onDragStart={startToolDrag(toolId)}
                aria-label={aria[toolId] ?? tool.nombre}
                title={`${etiquetas[toolId] ?? tool.nombre} · arrastra al tablero`}
              >
                {Icono ? <Icono size={19} /> : <Plus size={18} />}
                <span>{etiquetas[toolId] ?? tool.nombre}</span>
              </button>
            );
          })}
          <button type="button" className="board-rail-tool" onClick={() => setAddMenuOpen((open) => !open)} aria-haspopup="menu" aria-expanded={addMenuOpen} aria-label="Más herramientas" title="Más herramientas del registro">
            <Plus size={19} />
            <span>Más</span>
          </button>
        </aside>

      <main
        ref={viewportRef}
        tabIndex={0}
        aria-label="Lienzo del tablero"
        className={`board-viewport ${isPanning ? 'panning' : ''} ${spacePanActive ? 'space-pan' : ''} ${handMode ? 'hand-mode' : ''} ${connectMode ? 'connecting' : ''} ${frameToolId ? 'drawing-frame' : ''}`}
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget) return;
          if (event.key !== 'Tab' || event.shiftKey) return;
          const tarjetas = viewportRef.current?.querySelectorAll<HTMLElement>('[data-card-id]');
          if (!tarjetas?.length) return;
          event.preventDefault();
          const preferida = selectedCardIds.length
            ? viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${CSS.escape(selectedCardIds[0])}"]`)
            : null;
          (preferida ?? tarjetas[0]).focus();
        }}
        onPointerDown={beginViewportGesture}
        onPointerMove={moveViewportGesture}
        onPointerUp={endViewportGesture}
        onPointerCancel={endViewportGesture}
        onDragOver={(event) => {
          if (event.dataTransfer.types.includes('application/x-prometeo-tool') || event.dataTransfer.types.includes('Files')) {
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
          }
        }}
        onDrop={dropTool}
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
            <g ref={relationsRef}>
            {activeBoard.relations.map((relation) => {
              const from = activeBoard.cards.find((card) => card.id === relation.from);
              const to = activeBoard.cards.find((card) => card.id === relation.to);
              if (!from || !to) return null;
              const geo = geometriaConector(rectDeTarjeta(from), rectDeTarjeta(to));
              return (
                <g key={relation.id} className={`board-relation tone-${relation.tone ?? 'ember'}`}>
                  <path
                    className="board-relation-path"
                    d={geo.path}
                    markerEnd="url(#board-arrow)"
                    onDoubleClick={(event) => { event.stopPropagation(); editarEtiquetaRelacion(relation); }}
                  >
                    <title>{relation.label || 'Doble clic para etiquetar el conector'}</title>
                  </path>
                  {relation.label && (
                    <text className="board-relation-label" x={geo.medio.x} y={geo.medio.y} textAnchor="middle" dominantBaseline="middle" onDoubleClick={(event) => { event.stopPropagation(); editarEtiquetaRelacion(relation); }}>
                      {relation.label}
                    </text>
                  )}
                </g>
              );
            })}
            {connectDraft && (() => {
              const desde = activeBoard.cards.find((card) => card.id === connectDraft.from);
              if (!desde) return null;
              const geo = geometriaConector(rectDeTarjeta(desde), { x: connectDraft.mundo.x, y: connectDraft.mundo.y, width: 1, height: 1 });
              return <path className={`board-relation-draft ${connectDraft.target ? 'has-target' : ''}`} d={geo.path} />;
            })()}
            </g>
          </svg>
        <div className="board-stage" ref={stageRef}>
          {guias.x !== undefined && (
            <div className="board-guide board-guide-x" data-testid="board-guide-x" style={{ left: guias.x }} aria-hidden="true" />
          )}
          {guias.y !== undefined && (
            <div className="board-guide board-guide-y" data-testid="board-guide-y" style={{ top: guias.y }} aria-hidden="true" />
          )}
          {activeBoard.cards.map((card) => {
            const matches = matchingCards.has(card.id);
            if (card.type === 'columna') {
              const hijos = readColumnData(card).hijos
                .map((id) => cardsById.get(id))
                .filter((item): item is BoardCard => Boolean(item));
              return (
                <BoardColumn
                  key={card.id}
                  card={card}
                  childrenCards={hijos}
                  selected={selectedCardIds.includes(card.id)}
                  dimmed={!matches}
                  dragging={draggingIds.includes(card.id)}
                  settling={settlingIds.includes(card.id)}
                  dropTarget={dropFrameId === card.id}
                  onSelect={onCardSelect}
                  onDragStart={onCardDragStart}
                  onDragMove={onCardDragMove}
                  onDragEnd={onCardDragEnd}
                  onDelete={onCardDelete}
                  onPatch={onCardPatch}
                  onToggleFold={(id) => updateBoard((board) => ({ ...board, cards: setColumnFolded(board.cards, id, !readColumnData(card).plegada) }))}
                />
              );
            }
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
                  tabIndex={-1}
                  aria-selected={selectedCardIds.includes(card.id)}
                  aria-label={`Marco: ${card.title || 'sin título'}`}
                  className={`board-frame ${esEntropia ? 'is-entropia' : ''} ${collage?.guardado ? 'is-guardado' : ''} ${frame.vista === 'archivo' ? 'is-archive' : frame.vista === 'muro' ? 'is-muro' : frame.vista === 'mesa' ? 'is-mesa' : ''} ${selectedCardIds.includes(card.id) ? 'selected' : ''} ${!matches ? 'dimmed' : ''} ${draggingIds.includes(card.id) ? 'dragging' : ''} ${settlingIds.includes(card.id) ? 'settling' : ''} ${dropFrameId === card.id ? 'drop-target' : ''} ${card.locked ? 'is-locked' : ''}`}
                  style={{ left: card.x, top: card.y, width: card.width, height: frame.alto }}
                  onPointerMove={moveCardDrag}
                  onPointerUp={endCardDrag}
                  onPointerCancel={endCardDrag}
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
                  onBlurCapture={onCardBlur}
                  onKeyDown={(event) => {
                    if (event.target !== event.currentTarget) return;
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      handleCardSelection(card.id, event);
                    }
                  }}
                >
                  <div className="board-frame-head" onPointerDown={(event) => startCardDrag(card, event)} onPointerMove={moveCardDrag} onPointerUp={endCardDrag} onPointerCancel={endCardDrag} title="Arrastra para mover el marco y sus tarjetas">
                    <span className="board-drag-grip" aria-hidden="true">⠿</span>
                    <TituloEnSitio value={card.title} onCommit={(title) => updateCard(card.id, { title })} ariaLabel="Título del marco" className="board-frame-title" />
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
                    <button
                      type="button"
                      className="board-frame-lock"
                      onPointerDown={(event) => event.stopPropagation()}
                      onClick={(event) => { event.stopPropagation(); updateCard(card.id, { locked: !card.locked }); }}
                      aria-label={card.locked ? 'Desbloquear marco' : 'Bloquear marco'}
                      title={card.locked ? 'Desbloquear' : 'Bloquear posición, tamaño y borrado'}
                    >{card.locked ? <Lock size={13} /> : <LockOpen size={13} />}</button>
                    <button className="board-frame-delete" disabled={card.locked} onClick={(event) => { event.stopPropagation(); removeCard(card.id); }} aria-label="Eliminar marco" title="Eliminar el marco y dejar sus tarjetas"><X size={14} /></button>
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
                      <div className="board-frame-hint">Doble clic en el proyecto: pliego · en el encabezado: pantalla completa</div>
                    </>
                  ) : frame.vista === 'muro' ? (
                    <>
                      <MuroView frameTitle={card.title} cards={activeBoard.cards} childIds={frame.hijos} width={Math.max(180, card.width)} />
                      <div className="board-frame-hint">Clic en una miniatura: caja de luz · ← → recorren</div>
                    </>
                  ) : frame.vista === 'mesa' ? (
                    <MesaView frameTitle={card.title} cards={activeBoard.cards} childIds={frame.hijos} width={Math.max(180, card.width)} />
                  ) : (
                    <div className="board-frame-meta">{childCount} {childCount === 1 ? 'tarjeta' : 'tarjetas'} dentro</div>
                  )}
                  <button
                    type="button"
                    className="board-frame-resize"
                    onPointerDown={(event) => startFrameResize(card, event)}
                    onPointerMove={moveFrameResize}
                    onPointerUp={endFrameResize}
                    onPointerCancel={endFrameResize}
                    aria-label={`Redimensionar ${card.title || 'marco'}`}
                    title="Redimensionar marco"
                  />
                </article>
              );
            }
            // Los hijos de un marco con vista propia se pintan dentro del marco, no encima.
            if (framedChildIds.has(card.id)) return null;
            if (esMediaLibre(card)) {
              return (
                <BoardFreeMedia
                  key={card.id}
                  card={card}
                  selected={selectedCardIds.includes(card.id)}
                  dimmed={!matches}
                  dragging={draggingIds.includes(card.id)}
                  settling={settlingIds.includes(card.id)}
                  onSelect={onCardSelect}
                  onDragStart={onCardDragStart}
                  onDragMove={onCardDragMove}
                  onDragEnd={onCardDragEnd}
                   onDelete={onCardDelete}
                   onPatch={onCardPatch}
                   onResizeStart={startFreeResize}
                  onResizeMove={moveFreeResize}
                  onResizeEnd={endFreeResize}
                  onNaturalSize={ajustarAlturaNatural}
                />
              );
            }
            return (
              <BoardCardItem
                key={card.id}
                card={card}
                selected={selectedCardIds.includes(card.id)}
                dimmed={!matches}
                dragging={draggingIds.includes(card.id)}
                settling={settlingIds.includes(card.id)}
                 connectionSource={connectFromId === card.id}
                 connectionTarget={connectDraft?.target === card.id}
                 connectMode={connectMode}
                 colors={COLORS}
                 compact={zoom < 0.35}
                 onSelect={onCardSelect}
                 onConnect={onCardConnect}
                 onConnectStart={onCardConnectStart}
                onDragStart={onCardDragStart}
                onDragMove={onCardDragMove}
                onDragEnd={onCardDragEnd}
                onDelete={onCardDelete}
                onPatch={onCardPatch}
                onReplace={onCardReplace}
                onHover={onCardHover}
                onBlurCapture={onCardBlur}
              />
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

        {marquee && (
          <div
            className="board-marquee"
            data-testid="board-marquee"
            style={{ left: marquee.x, top: marquee.y, width: marquee.width, height: marquee.height }}
            aria-hidden="true"
          />
        )}

        <div className="board-count">
          {activeBoard.cards.length} {activeBoard.cards.length === 1 ? 'tarjeta' : 'tarjetas'} · arrastra el fondo para seleccionar · Espacio + arrastra para mover · ⌘/Ctrl + rueda para acercar
          <span data-testid="history-status" className="board-history-status" aria-live="polite">
            {historyStatus === 'nueva' ? ' · sesión nueva' : ' · historial restaurado'}
          </span>
        </div>
        <div className="sr-only" aria-live="polite" aria-atomic="true" data-testid="selection-live">
          {selectedCardIds.length === 0
            ? 'Sin selección'
            : `${selectedCardIds.length} ${selectedCardIds.length === 1 ? 'seleccionada' : 'seleccionadas'}`}
        </div>
      </main>

        <input ref={importInput} type="file" accept="application/json,.json,text/markdown,.md" hidden onChange={(event) => { void importBoard(event.target.files?.[0]); event.target.value = ''; }} />
        <input ref={mediaInput} type="file" accept="image/*,video/*,audio/*,application/pdf,text/plain,.txt" hidden onChange={(event) => { void addMedia(event.target.files?.[0]); event.target.value = ''; }} />
        <input ref={gustosInput} type="file" accept="application/json,.json" hidden aria-label="Archivo de gustos parciales" onChange={(event) => { void importGustos(event.target.files?.[0]); event.target.value = ''; }} />
      </div>

      {archiveFullscreenFrame && (
        <div ref={(element) => { dialogRef.current = element; }} className="board-archive-fullscreen" role="dialog" aria-modal="true" aria-label={`Archivo a pantalla completa: ${archiveFullscreenFrame.title || 'marco'}`}>
          <button type="button" className="archivo-fullscreen-close" onClick={() => setArchiveFullscreenId(null)}>Esc · volver a la pizarra</button>
          <ArchivoView
            frameTitle={archiveFullscreenFrame.title}
            cards={activeBoard.cards}
            childIds={readFrameData(archiveFullscreenFrame).hijos}
            fullscreen
          />
        </div>
      )}

      {selectedCards.length > 1 && (
        <div className="board-selection-bar" role="toolbar" aria-label={`Alinear ${selectedCards.length} tarjetas seleccionadas`}>
          <span className="board-selection-count">{selectedCards.length} seleccionadas</span>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('left')} aria-label="Alinear a la izquierda" title="Alinear a la izquierda">Izq</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('center-x')} aria-label="Centrar en vertical" title="Alinear los centros sobre el eje vertical">Centro</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('right')} aria-label="Alinear a la derecha" title="Alinear a la derecha">Der</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('top')} aria-label="Alinear arriba" title="Alinear arriba">Arriba</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('center-y')} aria-label="Centrar en horizontal" title="Alinear los centros sobre el eje horizontal">Medio</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('bottom')} aria-label="Alinear abajo" title="Alinear abajo">Abajo</button>
          <span className="board-tool-divider" aria-hidden="true" />
          <button type="button" className="board-selection-button" onClick={() => distributeSelection('horizontal')} disabled={selectedCardIds.length < 3} aria-label="Distribuir horizontalmente" title="Distribuir con espacios iguales en horizontal">↔</button>
          <button type="button" className="board-selection-button" onClick={() => distributeSelection('vertical')} disabled={selectedCardIds.length < 3} aria-label="Distribuir verticalmente" title="Distribuir con espacios iguales en vertical">↕</button>
          <span className="board-tool-divider" aria-hidden="true" />
          <button type="button" className="board-selection-button danger" onClick={deleteSelectedCards} aria-label="Eliminar tarjetas seleccionadas" title="Eliminar tarjetas seleccionadas"><Trash2 size={14} /></button>
        </div>
      )}

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

      {archiveOpen && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setArchiveOpen(false); }}>
          <div ref={(element) => { dialogRef.current = element; }} className="board-dialog board-dialog-wide board-archive-dialog" role="dialog" aria-modal="true" aria-labelledby="board-archive-title">
            <div className="board-dialog-heading">
              <h2 id="board-archive-title">Archivo</h2>
              <button type="button" onClick={() => setArchiveOpen(false)} aria-label="Cerrar Archivo"><X size={16} /></button>
            </div>
            <p className="board-dialog-hint">Lo que borras no desaparece del todo: queda aquí durante 30 días, sin papelera permanente.</p>
            <section className="board-archive-section" aria-labelledby="board-archive-recents">
              <div className="board-archive-section-head">
                <h3 id="board-archive-recents"><History size={15} aria-hidden="true" /> Recientes borrados</h3>
                <span>{borrados.length} {borrados.length === 1 ? 'entrada' : 'entradas'}</span>
              </div>
              {archiveError && <p className="board-dialog-error" role="alert">{archiveError}</p>}
              {borrados.length === 0 ? (
                <p className="board-archive-empty">Todavía no hay nada borrado en los últimos 30 días.</p>
              ) : (
                <ul className="board-archive-list" aria-label="Recientes borrados">
                  {borrados.map((entry) => {
                    const dias = Math.max(0, Math.ceil((Date.parse(entry.expiresAt) - Date.now()) / (24 * 60 * 60 * 1000)));
                    return (
                      <li key={entry.id} className="board-archive-item" data-borrado-kind={entry.kind} data-borrado-id={entry.id}>
                        <span className="board-archive-kind">{ETIQUETA_BORRADO[entry.kind]}</span>
                        <div className="board-archive-copy">
                          <strong>{entry.label}</strong>
                          <small>{new Date(entry.deletedAt).toLocaleString('es-ES', { dateStyle: 'medium', timeStyle: 'short' })} · quedan {dias} días</small>
                        </div>
                        <button type="button" className="board-tool primary" disabled={restoringId === entry.id} onClick={() => void restaurarEntrada(entry)}>
                          {restoringId === entry.id ? 'Restaurando…' : 'Restaurar'}
                        </button>
                        <button type="button" className="board-tool danger" onClick={() => void olvidarEntrada(entry.id)} aria-label={`Olvidar ${entry.label} para siempre`}>Olvidar</button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
            <div className="board-dialog-actions">
              <button type="button" className="board-tool primary" onClick={() => setArchiveOpen(false)}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {shortcutsOpen && (
        <div className="board-add-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShortcutsOpen(false); }}>
          <div ref={(element) => { dialogRef.current = element; }} className="board-dialog board-shortcuts" role="dialog" aria-modal="true" aria-labelledby="board-shortcuts-title">
            <div className="board-dialog-heading">
              <h2 id="board-shortcuts-title">Atajos del tablero</h2>
              <button type="button" onClick={() => setShortcutsOpen(false)} aria-label="Cerrar atajos"><X size={16} /></button>
            </div>
            <p className="board-dialog-hint">Los mismos gestos que ves en los controles, sin tener que buscarlos.</p>
            <div className="board-shortcuts-groups">
              {gruposDeAyuda().map((group) => (
                <section className="board-shortcuts-group" key={group.grupo} aria-label={group.grupo}>
                  <h3>{group.grupo}</h3>
                  <dl>
                    {group.items.map((atajo) => (
                      <div className="board-shortcut" key={atajo.id}>
                        <dt><kbd>{textoAtajo(atajo)}</kbd></dt>
                        <dd>{atajo.descripcion}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ))}
            </div>
            <div className="board-dialog-actions">
              <button type="button" className="board-tool primary" onClick={() => setShortcutsOpen(false)}>Entendido</button>
            </div>
          </div>
        </div>
      )}

      {addMenuOpen && (
        <div
          className="board-add-backdrop"
          onMouseDown={(event) => { if (event.target === event.currentTarget) setAddMenuOpen(false); }}
        >
          <div className="board-add-panel" role="presentation">
            <div className="board-add-heading">
              <span>Biblioteca de herramientas</span>
              <button type="button" onClick={() => setAddMenuOpen(false)} aria-label="Cerrar menú"><X size={15} /></button>
            </div>
            <BoardToolMenu onChoose={chooseTool} />
          </div>
        </div>
      )}

      {nestedDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setNestedDialog(false); }}>
          <div ref={(element) => { dialogRef.current = element; }} className="board-dialog board-dialog-wide" role="dialog" aria-modal="true" aria-labelledby="board-nested-title">
            <div className="board-dialog-heading"><h2 id="board-nested-title">Anidar un tablero</h2><button type="button" onClick={() => setNestedDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">La tarjeta guarda solo el vínculo. Al abrirla cambias de tablero sin perder lo que estabas mirando.</p>
            <div className="board-template-grid">
              {projectBoards.map((board) => (
                <button key={board.id} type="button" className="board-template-card" onClick={() => crearTableroAnidado(board)}>
                  <strong>{board.title || 'Sin título'}</strong>
                  <span>{board.cards.length} {board.cards.length === 1 ? 'tarjeta' : 'tarjetas'}</span>
                </button>
              ))}
            </div>
            <div className="board-dialog-actions"><button type="button" className="board-tool" onClick={() => setNestedDialog(false)}>Cancelar</button></div>
          </div>
        </div>
      )}

      {templateDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setTemplateDialog(false); }}>
          <div ref={(element) => { dialogRef.current = element; }} className="board-dialog board-dialog-wide" role="dialog" aria-modal="true" aria-labelledby="board-template-title">
            <div className="board-dialog-heading"><h2 id="board-template-title">Plantillas de tablero</h2><button type="button" onClick={() => setTemplateDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">Crear una plantilla no copia archivos: solo la estructura de tarjetas, columnas y tareas.</p>
            <div className="board-template-grid">
              {templates.map((plantilla) => (
                <div key={plantilla.id} className="board-template-card-wrap">
                  <button type="button" className="board-template-card" onClick={() => { void aplicarPlantilla(plantilla); }}>
                    <strong>{plantilla.nombre}</strong>
                    <span>{plantilla.descripcion}</span>
                    <small>{plantilla.builtin ? 'Incluida' : 'Guardada por ti'}</small>
                  </button>
                  {!plantilla.builtin && (
                    <button type="button" className="board-template-delete" onClick={() => borrarPlantillaGuardada(plantilla.id)} aria-label={`Eliminar plantilla ${plantilla.nombre}`} title="Eliminar plantilla guardada"><Trash2 size={12} /></button>
                  )}
                </div>
              ))}
            </div>
            <div className="board-dialog-actions">
              <button type="button" className="board-tool" onClick={guardarTableroComoPlantilla} disabled={!activeBoard}>Guardar este tablero como plantilla</button>
              <button type="button" className="board-tool primary" onClick={() => setTemplateDialog(false)}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {linkDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setLinkDialog(false); }}>
          <form ref={(element) => { dialogRef.current = element; }} className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="board-link-title" onSubmit={saveLinkCard}>
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
          <form ref={(element) => { dialogRef.current = element; }} className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="project-dialog-title" onSubmit={(event) => { void handleCreateProject(event); }}>
            <div className="board-dialog-heading"><h2 id="project-dialog-title">Crear proyecto</h2><button type="button" onClick={() => setProjectDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">Agrupa tableros y referencias PDF. Los archivos originales permanecen en su ubicación.</p>
            <label>Nombre del proyecto<input autoFocus required maxLength={120} value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Por ejemplo, Investigación" /></label>
            <div className="board-dialog-actions"><button type="button" className="board-tool" onClick={() => setProjectDialog(false)}>Cancelar</button><button type="submit" className="board-tool primary">Crear proyecto</button></div>
          </form>
        </div>
      )}

      {pdfReferenceDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setPdfReferenceDialog(false); }}>
          <form ref={(element) => { dialogRef.current = element; }} className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="pdf-reference-title" onSubmit={(event) => { void handleSavePdfReference(event); }}>
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
