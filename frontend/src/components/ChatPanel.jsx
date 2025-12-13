import React, { useState, useRef, useEffect } from 'react';
import useUIStore from '../store/uiStore';
import { runCommand, uploadFile, convertFile, splitLeft, maximizeWindow } from '../api';

const ChatPanel = ({ mode, setMode, onTogglePanel, panelState, setPanelState }) => {
    const { messages, setMessages, addMessage, isLoading, setLoading, setLatestResult, uploadProgress, setUploadProgress, attachmentPreview, setAttachmentPreview, setWingMode, switchChatHistory, commandHistory, addToHistory } = useUIStore();
    const [input, setInput] = useState('');
    const [uploadedFile, setUploadedFile] = useState(null); // Keeps track of last uploaded file URL
    const [showMenu, setShowMenu] = useState(false);
    const messagesEndRef = useRef(null);

    const [conversionProgress, setConversionProgress] = useState(0);

    // Hidden file input refs
    const glbInputRef = useRef(null);
    const stepInputRef = useRef(null);
    const bomInputRef = useRef(null);

    // Pending model for delayed loading logic
    const pendingModelUrl = useRef(null);

    // Local state for history navigation
    const [historyIndex, setHistoryIndex] = useState(-1);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // --- Main Interaction Handler ---
    const handleSend = async (manualCmd = null, hidden = false) => {
        const cmdToSend = (typeof manualCmd === 'string') ? manualCmd : input;

        // Only return if no command AND no file is attached. If file attached, we can proceed.
        if (!cmdToSend.trim() && !attachmentPreview) return;

        // Add to history if it's a manual command (text) and not empty
        if (cmdToSend.trim() && !manualCmd) {
            addToHistory(cmdToSend);
            setHistoryIndex(-1); // Reset index after send
        }

        // 1. Check for Mode Switching (only if no file attached)
        const lowerCmd = cmdToSend.toLowerCase();
        if (!attachmentPreview && lowerCmd.includes('switch') && (lowerCmd.includes('catia') || lowerCmd.includes('inhouse') || lowerCmd.includes('in-house') || lowerCmd.includes('incad') || lowerCmd.includes('cad'))) {
            if (!hidden) addMessage(cmdToSend, 'user');

            if (lowerCmd.includes('catia') && !lowerCmd.includes('inhouse')) {
                // Save current and switch to CATIA history
                switchChatHistory(mode, 'CATIA_COPILOT');
                setMode('CATIA_COPILOT');

                if (panelState !== 'left-maximized' && onTogglePanel) onTogglePanel();
                setTimeout(() => splitLeft(), 500);

            } else if (lowerCmd.includes('inhouse') || lowerCmd.includes('in-house') || lowerCmd.includes('incad')) {
                // Save current and switch to INHOUSE history
                switchChatHistory(mode, 'INHOUSE_CAD');
                setMode('INHOUSE_CAD');

                if (panelState === 'left-maximized' && onTogglePanel) onTogglePanel();
                setTimeout(() => maximizeWindow(), 500);
            }
            // If manually typed, clear input
            if (!manualCmd) setInput('');
            return;
        }

        // 2. Display User Interaction (File Card first, then Text)
        if (attachmentPreview && !hidden) {
            addMessage(null, 'user', { type: 'file_card', file: attachmentPreview.file });
        }
        if (cmdToSend.trim() && !hidden) {
            addMessage(cmdToSend, 'user');
        }

        if (!manualCmd) {
            setInput('');
            // Reset textarea height manually if needed
            const ta = document.querySelector('.pill-input-field');
            if (ta) ta.style.height = 'auto'; // Reset height
        }
        setLoading(true);

        // 3. Handle File Upload Sequence (if file exists)
        let currentUploadedUrl = null;
        let currentUploadFilename = null;
        let uploadSuccess = false;

        if (attachmentPreview) {
            try {
                // Clear viewer immediately on new upload start
                setLatestResult({ glb_url: null });

                setUploadProgress(0);

                // Simulate progress
                const progressInterval = setInterval(() => {
                    setUploadProgress(prev => Math.min(prev + 10, 90));
                }, 200);

                const res = await uploadFile(attachmentPreview.file, attachmentPreview.type);

                clearInterval(progressInterval);
                setUploadProgress(100);
                // Instant transition to 'done' state
                setUploadProgress(0);

                if (res.url) {
                    uploadSuccess = true;
                    currentUploadedUrl = res.url;
                    currentUploadFilename = res.filename || attachmentPreview.name;
                    setUploadedFile(res.url); // Update state

                    // Logic Distribution based on Type
                    if (attachmentPreview.type === 'step') {
                        // Check if command implies conversion. 
                        const isConvertIntent = !cmdToSend.trim() || lowerCmd.includes('convert') || lowerCmd.includes('glb');

                        if (isConvertIntent) {
                            // Start Conversion Flow
                            setConversionProgress(0);
                            const convInterval = setInterval(() => {
                                setConversionProgress(prev => {
                                    if (prev >= 90) return prev;
                                    return prev + 5;
                                });
                            }, 200);

                            const convRes = await convertFile(currentUploadFilename);

                            clearInterval(convInterval);
                            setConversionProgress(100);
                            setTimeout(() => setConversionProgress(0), 1000); // Hide bar after 1s

                            if (convRes.glb_url) {
                                pendingModelUrl.current = convRes.glb_url;

                                // Use original client-side filename for display
                                const originalName = attachmentPreview.name || 'model';
                                const baseName = originalName.lastIndexOf('.') !== -1 ? originalName.substring(0, originalName.lastIndexOf('.')) : originalName;
                                const friendlyFilename = `${baseName}.glb`;

                                // Show success and download
                                addMessage(`✅ Converted ${attachmentPreview.name} to GLB successfully.`, 'bot', {
                                    type: 'download_btn',
                                    url: convRes.glb_url,
                                    filename: friendlyFilename
                                });
                            } else {
                                addMessage(`❌ Conversion failed: ${convRes.error || 'Unknown error'}`, 'bot');
                            }
                        } else {
                            // Uploaded but not converting?
                            addMessage(`✅ Uploaded ${currentUploadFilename}. Say "convert" to process it.`, 'bot');
                        }
                    }
                    else if (attachmentPreview.type === 'glb') {
                        pendingModelUrl.current = res.url;
                        const isLoadIntent = !cmdToSend.trim() || lowerCmd.includes('load') || lowerCmd.includes('show') || lowerCmd.includes('visualize') || lowerCmd.includes('display');

                        if (isLoadIntent) {
                            setLatestResult({ glb_url: res.url });
                            addMessage('🚀 Loading model into viewer...', 'bot');
                            setPanelState('right-maximized');
                        } else {
                            addMessage(`✅ Uploaded ${currentUploadFilename}. Say "load model" to view.`, 'bot');
                        }
                    }

                } else {
                    addMessage(`❌ Error uploading file: ${res.error}`, 'bot');
                }
            } catch (error) {
                console.error("Upload error:", error);
                addMessage("❌ Error during upload process.", 'bot');
            } finally {
                // Clear attachment preview after processing (ALWAYS)
                setAttachmentPreview(null);
                setLoading(false);
            }
        } else {
            // No attachment, just stop loading if it was set
            setLoading(false);
        }

        // 4. Handle Backend Command (Text Only)
        if (!attachmentPreview && cmdToSend.trim()) {

            // --- WING OPTIMIZATION PRE-CHECK (Merged) ---
            // Check for explicit "wing" intent OR strong optimization keywords
            const hasWingKw = lowerCmd.includes("wing") || lowerCmd.includes("airfoil");
            const hasOptKw = lowerCmd.includes("optimize") || lowerCmd.includes("design") || lowerCmd.includes("make") || lowerCmd.includes("reduce") || lowerCmd.includes("maximize") || lowerCmd.includes("minimize") || lowerCmd.includes("find");
            const hasAeroContext = lowerCmd.includes("lift") || lowerCmd.includes("drag") || lowerCmd.includes("glider") || lowerCmd.includes("bending moment") || lowerCmd.includes("efficiency") || lowerCmd.includes("takeoff") || lowerCmd.includes("l/d");

            const isWingOpt = (hasWingKw && hasOptKw) || hasAeroContext;

            if (isWingOpt || lowerCmd.includes("run wing optimizer")) {
                // MODE CHECK: Only run In-House optimizer if mode is INHOUSE_CAD
                if (mode === 'INHOUSE_CAD') {
                    setWingMode(true);
                    addMessage("🚀 Starting Wing Optimization...", 'bot');
                    try {
                        const res = await fetch('http://127.0.0.1:8000/inhouse_cad/wing/optimize', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ prompt: cmdToSend })
                        });
                        const data = await res.json();
                        if (data.status === 'started') {
                            addMessage("Optimization started in background. Watching live updates in HUD.", 'bot');
                        } else {
                            addMessage(`Status: ${data.message}`, 'bot');
                        }
                    } catch (e) {
                        addMessage(`Error starting optimization: ${e}`, 'bot');
                    }
                    setLoading(false);
                    return; // Stop further processing for this command
                }
                // If mode is CATIA_COPILOT, fall through to handleSend -> runCommand logic below
            }
            // ------------------------------------------

            // ... Existing Visualization Check ...
            const glb_keywords = [
                "load glb", "load car model", "show glb", "display glb", "load model", "show model",
                "display model", "load 3d model", "show 3d model", "load this model", "show this model",
                "load uploaded model", "show the uploaded model in the in-house viewer",
                "show the uploaded model in the inhouse viewer", "visualize glb", "visualise glb",
                "visualize model", "visualise model", "visualize the converted step file",
                "visualise the converted step file", "visualize converted", "visualise converted",
                "visualize the recently converted step file", "visualize the recently converted step file", "load scooter glb model", "load dirt bike model", "load car model", "load truck model","implode model"];

            if (glb_keywords.some(k => lowerCmd.includes(k))) {
                if (pendingModelUrl.current) {
                    // Latest result trigger
                    setLatestResult({ glb_url: pendingModelUrl.current });
                    addMessage('🚀 Loading model into viewer...', 'bot');
                    setPanelState('right-maximized');
                } else {
                    addMessage('⚠️ No model is pending to load. Upload/Convert a file first.', 'bot');
                }
                return;
            }

            // ROTATE COMMAND: "Rotate 45 degree" or "Rotate -45" or "Rotate 45 clockwise"
            // Regex captures: 1=angle(incl negative), 2=unit(opt), 3=direction(opt)
            const rotateMatch = lowerCmd.match(/^rotate\s+(-?\d+)(?:\s*degrees?)?(?:\s*(clockwise|counter-clockwise|cw|ccw))?$/);
            if (rotateMatch) {
                let degrees = parseInt(rotateMatch[1], 10);
                const direction = rotateMatch[2];

                // Standard math: Positive is CCW.
                // If user says "Clockwise", we negate the angle (unless it's already negative, logic assumes user gives magnitude usually)
                // "Rotate 45 clockwise" -> -45
                // "Rotate -45 clockwise" -> 45 (double neg? usually means intent, let's assuming magnitude for direction context)
                // Let's keep it simple: Direction flips the sign of the parsed integer.
                if (direction && (direction === 'clockwise' || direction === 'cw')) {
                    degrees = -degrees;
                }

                const radians = degrees * (Math.PI / 180);
                useUIStore.getState().setModelRotation({ x: 0, y: radians, z: 0 });
                addMessage(`🔄 Rotating model by ${degrees}°`, 'bot');
                return;
            }

            // ... Existing Command Logic ...
            const catiaKeywords = ['wheel', 'rim', 'bom', 'bill of materials', 'catpart', 'catproduct', 'catia', 'wing', 'drone', 'bracket', 'l-bracket', 'multipart', 'assembly', 'rib', 'slot', 'topology'];
            const isCatiaCommand = catiaKeywords.some(keyword => cmdToSend.toLowerCase().includes(keyword));

            if (isCatiaCommand && mode === 'INHOUSE_CAD') {
                // Wing commands are handled above for INHOUSE_CAD, so if we reach here with 'wing', it means it wasn't caught by optimization (unlikely if 'wing' is kw)
                // OR it's another catia command.
                // Wait, 'wing' is in catiaKeywords. If we skipped the block above (e.g. no optimize kw?), we might hit this.
                // If user says just "wing", isWingOpt might be false. 
                // But let's assume if it fell through, it's not a generic in-house opt command. 
                // We can allow it to warn usage of Catia mode.
                addMessage('⚠️ This command requires CATIA mode. Please type "switch to catia" first.', 'bot');
                return;
            }

            const commonKeywords = ['load glb', 'show glb', 'view', 'display', 'rotate', 'zoom', 'transform', 'move', 'scale', 'measure', 'explode', 'color'];
            const isCommonCommand = commonKeywords.some(keyword => cmdToSend.toLowerCase().includes(keyword));

            // Quick frontend-only commands (Measure, Transform, Explode, Color)
            // These should NOT go to backend processing necessarily if they are purely UI toggles,
            // BUT existing logic often sends them to backend too, or handles them locally.
            // User's snippet didn't have specific blocks for them, suggesting they depend on backend 'runCommand' OR 
            // they were omitted. The PREVIOUS code had specific blocks for them.
            // "if anything from existing code is missing add them to these"
            // I should RESTORE the UI toggle blocks.

            if (lowerCmd.includes("measure")) {
                useUIStore.getState().setMeasureMode(true);
                addMessage("📏 Measurement Mode Active. Click two points on the model.", 'bot');
                setLoading(false);
                return;
            }
            if (lowerCmd.includes("transform") || lowerCmd.includes("rotate") || lowerCmd.includes("scale") || lowerCmd.includes("move")) {
                useUIStore.getState().setTransformMode(true);
                addMessage("🔄 Transform Controls Enabled. You can now Rotate/Scale/Move components.", 'bot');
                setLoading(false);
                return;
            }

            // --- EXPLODE & COLOR (Local Intercept for Full Screen) ---
            if (lowerCmd.includes("explode")) {
                useUIStore.getState().setExplodeMode(true);
                setPanelState('right-maximized'); // Expand to full screen
                addMessage("💥 Explode View Active. Model expanded in full screen.", 'bot');
                setLoading(false);
                return;
            }

            if (lowerCmd.includes("color") || lowerCmd.includes("apply color")) {
                useUIStore.getState().setColorMode(true);
                setPanelState('right-maximized'); // Expand to full screen
                addMessage("🎨 Color Analysis Mode Active. Model expanded in full screen.", 'bot');
                setLoading(false);
                return;
            }

            // --- VIEW CONTROL COMMANDS ---
            const viewMatch = lowerCmd.match(/\b(top|bottom|front|back|left|right|rear|side)\s+view\b/);
            if (viewMatch) {
                let viewDirection = viewMatch[1];
                if (viewDirection === 'rear') viewDirection = 'back';
                if (viewDirection === 'side') viewDirection = 'right';

                useUIStore.getState().setRequestedView(viewDirection);
                setPanelState('right-maximized');
                addMessage(` Switching to ${viewDirection.charAt(0).toUpperCase() + viewDirection.slice(1)} View`, 'bot');
                setLoading(false);
                return;
            }

            setLoading(true);
            // We pass 'uploadedFile' state which might persist from previous uploads
            const res = await runCommand(cmdToSend, { uploaded_file: uploadedFile });
            setLoading(false);

            // --- Handle Backend Modes ---
            if (res.mode === 'explode') {
                useUIStore.getState().setExplodeMode(true); // or toggle
            }
            if (res.mode === 'apply_colors') {
                useUIStore.getState().setColorMode(true);
            }

            if (res.output || res.mode === 'optimization_cards') {
                if (res.downloads?.csv || res.downloads?.pdf || res.downloads?.xlsx) {
                    addMessage('✅ Task done successfully', 'bot', { type: 'downloads', items: res.downloads });
                } else if (res.mode === 'optimization_cards') {
                    addMessage(res.raw_text || "Optimization Results:", 'bot', { type: 'optimization_cards', options: res.options });
                } else {
                    addMessage(res.output || '✅ Task done successfully', 'bot');
                }
            } else {
                addMessage('✅ Task done successfully', 'bot');
            }
            setLatestResult(res);
        }
    };

    const handleGenerateDesign = async (card) => {
        // 1. Determine Script Name
        let scriptName = "catia_create_parts_dynamic.py"; // Default: Cylinder Solid

        if (card.shape_type === 'cylinder_tube') {
            scriptName = "catia_create_parts_dynamic_updated.py";
        } else if (card.shape_type === 'rect_rod' || (card.shape_type && card.shape_type.includes('rect') && !card.shape_type.includes('tube'))) {
            scriptName = "catia_create_parts_dynamic_rectrod.py";
        } else if (card.shape_type === 'rect_tube' || (card.shape_type && card.shape_type.includes('rect') && card.shape_type.includes('tube'))) {
            scriptName = "catia_create_parts_dynamic_rectrod_updated.py";
        } else if (card.shape_type === 'wing') {
            scriptName = "wing_structure_winglet_transparent.py";
        }

        // 2. Map Params
        const params = {
            // Common
            plate_width: card.width_mm || card.base_width_mm || 150,
            plate_length: card.length_mm || card.base_length_mm || 200,
            pad_thickness: card.thickness_mm || card.base_thickness_mm || 20,

            // Positioning (default centered)
            pos_x: 0,
            pos_y: 0,
            corner_offset: 5,
            hole_diameter: 5,

            // Cylinder
            cyl_radius: (card.cyl_diameter || card.cylinder_diameter_mm || 50) / 2.0,
            cyl_height: card.cyl_height || card.cylinder_height_mm || 100,

            // Rect Rod/Tube
            rod_w: card.rod_w_mm || 50,
            rod_d: card.rod_d_mm || 40,
            rod_h: card.rod_h_mm || 100,

            // Wall (Tubes)
            wall_thickness: card.wall_mm || 2,
            wall: card.wall_mm || 2,

            // Wing
            m: card.m || 4,
            p: card.p || 4,
            t: card.t || 12,
            c_t: card.c_t || 0.5,
            a_sweep: card.sweep || 35.0,
            // Defaults for wing script if not in card
            c_r: 1.75,
            s: 3.0,
            Nribs: 10,
            Dholes: 0.8,
            xc_spar_1: 0.25,
            xc_spar_2: 0.75,
            t_rib: 0.01
        };

        // Scripts expect specific keys:
        // dynamic.py / updated.py (Cyl): uses plate_width/height (check implementation, usually it's compatible)
        // If script uses "plate_width" but some use "width", we might need to be careful.
        // Assuming the scripts align with this common superset or we rely on them being updated.
        // Note: The original prompt_router used build_flags_for_multipart which did: "plate_w": ...
        // I will add aliases to be safe.
        params["plate_w"] = params.plate_width;
        params["plate_l"] = params.plate_length;
        params["plate_t"] = params.pad_thickness;

        addMessage(`⚙️ Generating ${card.shape_type || 'design'} logic...`, 'bot');
        setLoading(true);

        try {
            const response = await fetch('http://127.0.0.1:8000/execute_catia_script', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    script_name: scriptName,
                    params: params
                })
            });

            const data = await response.json();
            if (data.success) {
                addMessage(`✅ Generation Successful!\n${data.output}`, 'bot');
            } else {
                addMessage(`❌ Generation Failed: ${data.message}`, 'bot');
            }
        } catch (e) {
            addMessage(`❌ Error: ${e.message}`, 'bot');
        }
        setLoading(false);
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
            return;
        }

        if (e.key === 'ArrowUp') {
            e.preventDefault();
            const len = commandHistory.length;
            if (len === 0) return;

            let newIndex = historyIndex;
            if (newIndex === -1) {
                newIndex = len - 1; // Start from end
            } else {
                newIndex = Math.max(0, newIndex - 1);
            }
            setHistoryIndex(newIndex);
            setInput(commandHistory[newIndex]);
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            const len = commandHistory.length;
            if (len === 0 || historyIndex === -1) return;

            let newIndex = historyIndex + 1;
            if (newIndex >= len) {
                newIndex = -1; // Reset to blank
                setInput('');
            } else {
                setInput(commandHistory[newIndex]);
            }
            setHistoryIndex(newIndex);
        }
    };

    // Force download with correct name (bypass CORS/Content-Disposition issues)
    const handleDownload = async (url, filename) => {
        try {
            const response = await fetch(url);
            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(blobUrl);
        } catch (err) {
            console.error("Download failed:", err);
            // Fallback
            window.open(url, '_blank');
        }
    };

    // Upload Handlers - STAGES ONLY
    const handleFileUpload = (e, type) => {
        const file = e.target.files?.[0];
        if (!file) return;

        // Just stage the file
        setAttachmentPreview({ name: file.name, file, type });

        // Reset input to allow re-selecting same file if needed (after it's cleared)
        e.target.value = null;
    };

    const handleAddTask = () => {
        const task = prompt("Enter new task capability:");
        if (task) {
            addMessage(`Added new task capability: "${task}"`, 'bot');
        }
    };

    const handleRemoveAttachment = () => {
        setAttachmentPreview(null);
        setUploadedFile(null); // Optional: clear previous uploaded file context too?
    };

    const handleClearChat = () => {
        setMessages([]);
    };

    return (
        <div className="chat-panel-container" onClick={() => setShowMenu(false)}>
            <div className="chat-wrapper">
                {/* Header */}
                <div className="new-panel-header">
                    <div className="brand-section">
                        <div className="brand-logo-title" style={{ gap: '12px' }}>
                            <div className="brand-text">
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0px' }}>
                                    <div className="brand-title">PeopleCAD</div>
                                    <img src="image (2).png" alt="PeopleCAD" className="brand-logo-img" style={{ height: '43px' }} />
                                </div>
                                <div className="brand-tagline">Design Smarter. Build Faster</div>
                            </div>
                        </div>
                    </div>
                    <div className="header-actions">
                        <button className="expand-btn" onClick={(e) => { e.stopPropagation(); handleClearChat(); }} title="Clear Chat" style={{ marginRight: '8px' }}>
                            <i className="fas fa-sync-alt"></i>
                        </button>
                        <button className="expand-btn" onClick={(e) => { e.stopPropagation(); onTogglePanel(); }} title="Maximize Chat">
                            <i className={`fas ${panelState === 'left-maximized' ? 'fa-compress' : 'fa-expand'}`}></i>
                        </button>
                    </div>
                </div>
 

                {/* Chat Area */}
                <div className="chat-history">
                    {messages.map((msg) => (
                        <div key={msg.id} className={`chat-msg ${msg.sender}`}>
                            {msg.text}
                            {msg.action && (
                                <div style={{ marginTop: '5px', display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                                    {msg.action.type === 'downloads' ? (
                                        <>
                                            {msg.action.items.csv && (
                                                <button className="bom-btn" onClick={() => window.open(msg.action.items.csv, '_blank')}>⬇ CSV</button>
                                            )}
                                            {msg.action.items.xlsx && (
                                                <button className="bom-btn" onClick={() => window.open(msg.action.items.xlsx, '_blank')}>⬇ XLSX</button>
                                            )}
                                            {msg.action.items.pdf && (
                                                <button className="bom-btn" onClick={() => window.open(msg.action.items.pdf, '_blank')}>⬇ PDF</button>
                                            )}
                                        </>
                                    ) : msg.action.type === 'optimization_cards' ? (
                                        <div className="opt-cards-container">
                                            {msg.action.options.map((opt, i) => (
                                                <div key={i} className="opt-card">
                                                    <div className="card-header">
                                                        <div className="design-title">{opt.design_name || `Design #${i + 1}`}</div>
                                                    </div>
                                                    <div className="card-body">
                                                        {opt.shape_type === 'wing' ? (
                                                            <>
                                                                <div className="param-row">Params: M={opt.m}, P={opt.p}, T={opt.t}%</div>
                                                                <div className="param-row">Tip Chord: {opt.c_t} m, Sweep: {opt.sweep}°</div>
                                                                <div className="metric-row" style={{ marginTop: '8px', fontWeight: 'bold', color: '#22c55e' }}>
                                                                    Score: {Number(opt.score).toFixed(2)}
                                                                </div>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <div className="param-row">
                                                                    Base: {Math.round(opt.length_mm || opt.base_length_mm)}x{Math.round(opt.width_mm || opt.base_width_mm)}x{Math.round(opt.thickness_mm || opt.base_thickness_mm)} mm
                                                                </div>
                                                                {(opt.shape_type === 'cylinder_solid' || opt.shape_type === 'cylinder_tube' || (opt.cyl_diameter)) && (
                                                                    <div className="param-row">
                                                                        Cyl: Ø{Math.round(opt.cyl_diameter || opt.cylinder_diameter_mm)} x {Math.round(opt.cyl_height || opt.cylinder_height_mm)} mm
                                                                    </div>
                                                                )}

                                                                {opt.shape_type === 'wing' && (
                                                                    <>
                                                                        <div className="param-row">m (max camber %): {opt.m}</div>
                                                                        <div className="param-row">p (camber pos): {opt.p}</div>
                                                                        <div className="param-row">t (thickness %): {opt.t}</div>
                                                                        <div className="param-row">c_t (tip chord m): {opt.c_t}</div>
                                                                        <div className="param-row">sweep (deg): {opt.sweep}</div>
                                                                    </>
                                                                )}

                                                                <div className="metric-row" style={{ marginTop: '8px', fontWeight: 'bold', color: '#22c55e' }}>
                                                                    {opt.search_type === 'wing' ? `Score: ${Number(opt.score).toFixed(4)}` : (opt.weight_kg ? `Weight: ${Number(opt.weight_kg).toFixed(3)} kg` : '')}
                                                                </div>
                                                            </>
                                                        )}
                                                        <div className="metric-row" style={{ color: '#ccc' }}>
                                                            Score: {Number(opt.score).toFixed(2)}
                                                        </div>

                                                        <button className="opt-generate-btn" onClick={() => handleGenerateDesign(opt)}>Generate in CATIA</button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : msg.action.type === 'file_card' ? (
                                        <div className="file-card-bubble" style={{
                                            display: 'flex', alignItems: 'center', gap: '10px',
                                            background: 'rgba(255,255,255,0.1)', padding: '10px 14px',
                                            borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)'
                                        }}>
                                            <div style={{ background: '#3b82f6', width: '36px', height: '36px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                <i className="fas fa-file" style={{ color: 'white' }}></i>
                                            </div>
                                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                                                <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'white' }}>{msg.action.file.name}</span>
                                                <span style={{ fontSize: '0.75rem', color: '#ccc' }}>
                                                    {/* Safe fallback for size in case file object is simple struct */}
                                                    {msg.action.file.size ? (msg.action.file.size / 1024).toFixed(1) + ' KB' : 'File'}
                                                </span>
                                            </div>
                                        </div>
                                    ) : msg.action.type === 'download_btn' ? (
                                        <div style={{ marginTop: '8px', width: '100%' }}>
                                            <a
                                                href={msg.action.url}
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    handleDownload(msg.action.url, msg.action.filename);
                                                }}
                                                style={{
                                                    textDecoration: 'none',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    gap: '8px',
                                                    width: '100%',
                                                    padding: '12px',
                                                    background: '#5ea2d6',
                                                    color: 'white',
                                                    borderRadius: '8px',
                                                    fontWeight: '600',
                                                    boxSizing: 'border-box',
                                                    cursor: 'pointer'
                                                }}
                                            >
                                                <i className="fas fa-download"></i> Download {msg.action.filename}
                                            </a>
                                        </div>
                                    ) : (
                                        <button
                                            className="bom-btn"
                                            onClick={msg.action.onClick}
                                        >
                                            {msg.action.label}
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                    {isLoading && (
                        <div style={{ padding: '10px', color: '#666', fontSize: '0.8rem' }}>Processing...</div>
                    )}
                    {/* Conversion Progress Bar in Chat */}
                    {conversionProgress > 0 && conversionProgress <= 100 && (
                        <div className={`chat-msg bot`}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', minWidth: '240px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                    <i className="fas fa-cog fa-spin" style={{ color: 'var(--accent-blue)', fontSize: '1.1em' }}></i>
                                    <span style={{ fontWeight: 600, color: '#fff' }}>Converting Model...</span>
                                    <span style={{ marginLeft: 'auto', fontFamily: 'monospace', color: 'var(--accent-blue)' }}>{conversionProgress}%</span>
                                </div>
                                <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden', marginTop: '4px' }}>
                                    <div style={{ width: `${conversionProgress}%`, height: '100%', background: 'var(--accent-blue)', transition: 'width 0.2s ease' }}></div>
                                </div>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="new-input-area">
                    {/* Attachment Preview - Only show if not empty */}
                    {attachmentPreview && (
                        <div className="attachment-preview">
                            <div className="icon">
                                {uploadProgress > 0 && uploadProgress < 100 ? (
                                    <div className="upload-spinner"></div>
                                ) : (
                                    <i className="fas fa-file"></i>
                                )}
                            </div>
                            <div className="file-info">
                                <div className="name">{attachmentPreview.name}</div>
                                <div className="file-type">File</div>
                            </div>
                            {/* Always show close button unless strictly loading? Usually shown so user can cancel. 
                                User asked for 'loading then file'. Let's keep close button available appropriately. 
                                Actually, standard is to allow cancel during load, but simpler to just show close when done? 
                                Let's show close button ALWAYS for simplicity unless logic dictates otherwise. 
                                previous code hid it during success. Now success is gone. 
                            */}
                            <div className="close" onClick={handleRemoveAttachment} title="Remove attachment">
                                <i className="fas fa-times-circle"></i>
                            </div>
                        </div>
                    )}

                    <div className="plus-menu-container">
                        <div className="input-bar-pill">
                            <button
                                className="plus-btn"
                                onClick={(e) => { e.stopPropagation(); setShowMenu(!showMenu); }}
                                style={{ fontSize: '1.2rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                            >
                                <i className="fas fa-plus"></i>
                            </button>
                            {showMenu && (
                                <div className="plus-menu-dropdown" onClick={(e) => e.stopPropagation()}>
                                    {mode === 'INHOUSE_CAD' ? (
                                        // In-house CAD mode: Show only GLB and STEP upload
                                        <>
                                            <div className="pm-item" onClick={() => { glbInputRef.current?.click(); setShowMenu(false); }}>
                                                <i className="fas fa-cube" style={{ color: '#0ea5e9', marginRight: '8px' }}></i> Upload GLB
                                            </div>
                                            <div className="pm-item" onClick={() => { stepInputRef.current?.click(); setShowMenu(false); }}>
                                                <i className="fas fa-cog" style={{ color: '#0ea5e9', marginRight: '8px' }}></i> Upload STEP
                                            </div>
                                        </>
                                    ) : (
                                        // CATIA mode: Show only BOM and Add Task
                                        <>
                                            <div className="pm-item" onClick={() => { bomInputRef.current?.click(); setShowMenu(false); }}>
                                                <i className="fas fa-file-alt" style={{ color: '#0ea5e9', marginRight: '8px' }}></i> Upload CADPart
                                            </div>
                                            <div className="pm-item" onClick={() => { handleAddTask(); setShowMenu(false); }}>
                                                <i className="fas fa-plus-circle" style={{ color: '#0ea5e9', marginRight: '8px' }}></i> Add Task
                                            </div>
                                        </>
                                    )}
                                </div>
                            )}
                            <textarea
                                className="pill-input-field"
                                placeholder={attachmentPreview ? "Describe what to do with this file..." : "Ask anything..."}
                                value={input}
                                onChange={(e) => {
                                    setInput(e.target.value);
                                    e.target.style.height = 'auto';
                                    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                                }}
                                onKeyDown={handleKeyDown}
                                rows={1}
                                style={{
                                    minHeight: '40px',
                                    maxHeight: '120px',
                                    overflowY: 'auto',
                                    resize: 'none',
                                    paddingTop: '10px'
                                }}
                            />
                            <button className="pill-send-btn" onClick={() => handleSend()} disabled={isLoading}>
                                <i className="fas fa-arrow-up"></i>
                            </button>
                        </div>
                    </div>

                    {/* Upload Progress - Bottom Indicator */}
                    {uploadProgress > 0 && uploadProgress < 100 && (
                        <div className="upload-progress-container">
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Uploading...</span>
                                <span style={{ fontSize: '0.8rem', color: '#fff' }}>{uploadProgress}%</span>
                            </div>
                            <div className="upload-progress-bar">
                                <div className="upload-progress-fill" style={{ width: `${uploadProgress}%` }}></div>
                            </div>
                        </div>
                    )}

                    {/* CAD Model Status */}
                    <div className="cad-model-status">
                        <i className="fas fa-cube" style={{ color: 'var(--accent-blue)', fontSize: '1.1rem' }}></i>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <span style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>Current CAD engine:</span>
                            <span style={{ color: '#d4ffe4', fontWeight: 600, fontSize: '0.95rem' }}>
                                {mode === 'CATIA_COPILOT' ? 'CATIA' : 'In-house CAD'}
                            </span>
                        </div>
                    </div>

                    {/* Hidden Inputs */}
                    <input type="file" accept=".glb,.gltf" ref={glbInputRef} style={{ display: 'none' }} onChange={(e) => handleFileUpload(e, 'glb')} />
                    <input type="file" accept=".step,.stp" ref={stepInputRef} style={{ display: 'none' }} onChange={(e) => handleFileUpload(e, 'step')} />
                    <input type="file" accept=".txt,.csv,.json" ref={bomInputRef} style={{ display: 'none' }} onChange={(e) => handleFileUpload(e, 'bom')} />
                </div>
            </div>
        </div>
    );
};

export default ChatPanel;
