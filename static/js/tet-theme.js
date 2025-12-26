/**
 * Tết 2026 Theme Module
 * Year of the Horse (Bính Ngọ)
 * High-performance festive theme for Map-Routing application
 */

class TetTheme {
    constructor() {
        this.canvas = null;
        this.ctx = null;
        this.petals = [];
        this.animationId = null;
        this.maxPetals = 30; // Limit for performance
        this.lanternsCreated = false;
        this.countdownTimer = null;
        this.toastShown = false;
        this.fireworksCanvas = null;
        this.fireworksCtx = null;
        this.fireworks = [];
        this.mapFrameCreated = false;
        
        // Lunar New Year 2026: February 17, 2026 00:00:00 (Vietnam time, UTC+7)
        this.tetDate = new Date('2026-02-17T00:00:00+07:00');
        
        this.init();
    }
    
    init() {
        // Wait for DOM and Leaflet to be ready
        // TetTheme script được load cuối cùng, nhưng vẫn đảm bảo chờ DOMContentLoaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                // Thêm delay nhỏ để đảm bảo Leaflet đã load
                setTimeout(() => this.setup(), 100);
            });
        } else {
            // DOM đã ready, nhưng vẫn chờ Leaflet
            setTimeout(() => this.setup(), 100);
        }
    }
    
    setup() {
        this.createBlossomCanvas();
        this.createFireworksCanvas();
        this.createLanterns();
        this.createMapFrame();
        this.createTetBorderFrame(); // New: Tạo khung viền Tết với hoa mai vàng
        this.createCherryBranchCorners(); // Create Cherry Blossom branches at corners using Lottie
        this.createSidebarBlossoms(); // Create falling blossoms inside sidebar
        this.createPopupBlossoms(); // Create falling blossoms inside popups
        this.createGreetingHeader();
        this.createCountdown();
        // Removed showGreetingToast() - not needed on startup
        this.startBlossomAnimation();
        
        // REMOVED: this.setupToggleButton(); // XÓA - Để DaisyUI tự quản lý drawer
    }
    
    /**
     * Create Cherry Blossom Branches at corners using Lottie
     */
    createCherryBranchCorners() {
        // Đợi Lottie library sẵn sàng
        setTimeout(() => {
            // Check if lottie is available
            if (typeof lottie === 'undefined') {
                console.warn('Lottie library not loaded. Retrying...');
                setTimeout(() => this.createCherryBranchCorners(), 500);
                return;
            }
            
            // Check if already created
            if (document.querySelector('.cherry-branch-top-left')) {
                return; // Already created
            }
            
            // Top-left branch container (chỉ góc trên trái)
            const topLeftWrapper = document.createElement('div');
            topLeftWrapper.className = 'cherry-branch-container cherry-branch-top-left';
            
            // Lottie target div cho góc trên trái
            const topLeftTarget = document.createElement('div');
            topLeftTarget.className = 'lottie-target';
            topLeftTarget.id = 'lottie-top-left';
            topLeftWrapper.appendChild(topLeftTarget);
            document.body.appendChild(topLeftWrapper);
            
            // Load Lottie animation cho góc trên trái
            const animConfig = {
                renderer: 'svg',
                loop: true,
                autoplay: true,
                path: '/Components/Cherry%20Blossom.json' // Path to JSON file (URL encoded space)
            };
            
            // Load top-left animation
            try {
                lottie.loadAnimation({
                    ...animConfig,
                    container: topLeftTarget
                });
            } catch (e) {
                console.warn('Failed to load top-left cherry blossom:', e);
            }
        }, 500);
    }
    
    /**
     * Create HTML5 Canvas for falling blossoms (high performance)
     */
    createBlossomCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.id = 'blossom-canvas';
        this.canvas.style.position = 'fixed';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.zIndex = '300'; // Layer 4: Top layer - Falling petals above everything
        this.canvas.style.pointerEvents = 'none';
        document.body.appendChild(this.canvas);
        
        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
        
        window.addEventListener('resize', () => this.resizeCanvas());
    }
    
    resizeCanvas() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    /**
     * Create animated lanterns at top corners
     */
    createLanterns() {
        if (this.lanternsCreated) return;
        
        const leftLantern = document.createElement('div');
        leftLantern.className = 'tet-lantern left';
        document.body.appendChild(leftLantern);
        
        const rightLantern = document.createElement('div');
        rightLantern.className = 'tet-lantern right';
        document.body.appendChild(rightLantern);
        
        this.lanternsCreated = true;
    }
    
    /**
     * Create magnificent map frame with Vạn pattern, horses, and blossoms
     */
    createMapFrame() {
        if (this.mapFrameCreated) return;
        
        const mapContainer = document.getElementById('map');
        if (!mapContainer) return;
        
        // Wrap map in container if not already
        const existingContainer = mapContainer.parentElement;
        if (!existingContainer || existingContainer.id !== 'map-container') {
            const container = document.createElement('div');
            container.id = 'map-container';
            mapContainer.parentNode.insertBefore(container, mapContainer);
            container.appendChild(mapContainer);
        }
        
        // Create frame element
        const frame = document.createElement('div');
        frame.id = 'map-frame';
        
        // Create borders
        const borders = ['top', 'bottom', 'left', 'right'];
        borders.forEach(side => {
            const border = document.createElement('div');
            border.className = `map-frame-border ${side}`;
            frame.appendChild(border);
        });
        
        // Create horse medallions at corners
        const corners = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
        corners.forEach(corner => {
            const medallion = document.createElement('div');
            medallion.className = `horse-medallion ${corner}`;
            medallion.innerHTML = this.getHorseSVG();
            frame.appendChild(medallion);
        });
        
        const container = document.getElementById('map-container');
        if (container) {
            container.appendChild(frame);
        }
        
        this.mapFrameCreated = true;
    }
    
    /**
     * Get SVG for Golden Horse (Bính Ngọ)
     */
    getHorseSVG() {
        return `
            <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="horseGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#FFD700;stop-opacity:1" />
                        <stop offset="100%" style="stop-color:#FFA500;stop-opacity:1" />
                    </linearGradient>
                </defs>
                <!-- Horse silhouette -->
                <path d="M 30 60 Q 25 40 35 30 Q 45 20 55 25 Q 65 30 70 35 Q 75 40 75 50 Q 75 60 70 65 Q 65 70 55 75 Q 45 80 35 75 Q 25 70 30 60 Z" 
                      fill="url(#horseGrad)" 
                      stroke="#D80000" 
                      stroke-width="2"/>
                <!-- Mane -->
                <path d="M 35 30 Q 30 20 40 15 Q 50 10 55 20" 
                      fill="url(#horseGrad)" 
                      stroke="#D80000" 
                      stroke-width="1.5"/>
                <!-- Eye -->
                <circle cx="50" cy="40" r="3" fill="#D80000"/>
            </svg>
        `;
    }
    
    /**
     * Create Tet Border Frame with Golden Apricot Blossoms (Hoa Mai Vàng)
     * Layer 2: Middle Layer - Red Frame with Yellow Flowers (Background for falling petals)
     * Khung viền Tết với hoa mai vàng - Balanced highlights, not dense clusters
     */
    createTetBorderFrame() {
        // Create main frame container
        const frameContainer = document.createElement('div');
        frameContainer.id = 'tet-border-frame';
        frameContainer.className = 'tet-border-frame';
        
        // Calculate responsive border thickness
        const isMobile = window.innerWidth < 768;
        const borderThickness = isMobile ? 40 : 55; // Cập nhật thickness: DÀY lên 55px
        frameContainer.style.setProperty('--border-thickness', `${borderThickness}px`);
        
        // Tăng số lượng hoa và size
        const sides = [
            { 
                name: 'top', 
                flowers: 10,  // Tăng từ 7 lên 10
                sizeRange: [22, 32] // Tăng size từ [18,28] lên [22,32]
            },
            { 
                name: 'bottom', 
                flowers: 10,  // Tăng từ 7 lên 10
                sizeRange: [22, 32]
            },
            { 
                name: 'left', 
                flowers: 5,  // Tăng từ 3 lên 5
                sizeRange: [20, 28]
            },
            { 
                name: 'right', 
                flowers: 5,  // Tăng từ 3 lên 5
                sizeRange: [20, 28]
            }
        ];
        
        sides.forEach(side => {
            const border = document.createElement('div');
            border.className = `tet-border-side tet-border-${side.name}`;
            
            // Create flowers with random positioning
            for (let i = 0; i < side.flowers; i++) {
                const flower = document.createElement('div');
                flower.className = 'tet-mai-flower';
                
                // Random position along the side (5% to 95% to avoid exact corners)
                const position = 5 + Math.random() * 90;
                flower.style.setProperty('--position', `${position}%`);
                
                // Vary flower size
                const size = side.sizeRange[0] + Math.random() * (side.sizeRange[1] - side.sizeRange[0]);
                flower.style.width = `${size}px`;
                flower.style.height = `${size}px`;
                
                // Random rotation for natural look
                const rotation = Math.random() * 360;
                flower.style.setProperty('--rotation', `${rotation}deg`);
                
                // Random delay for animation
                flower.style.animationDelay = `${Math.random() * 2}s`;
                
                // Slight random offset from center for natural placement
                const offset = (Math.random() - 0.5) * 8; // ±4px offset
                flower.style.setProperty('--offset', `${offset}px`);
                
                border.appendChild(flower);
            }
            
            frameContainer.appendChild(border);
        });
        
        document.body.appendChild(frameContainer);
        
        // Update on resize
        window.addEventListener('resize', () => {
            const isMobile = window.innerWidth < 768;
            const borderThickness = isMobile ? 40 : 55;
            frameContainer.style.setProperty('--border-thickness', `${borderThickness}px`);
        });
    }
    
    /**
     * Create falling blossoms inside Leaflet Popups
     */
    createPopupBlossoms() {
        // Wait for map to be initialized, then listen for popup open events
        const checkMapAndSetup = () => {
            // Try to get map from window or global scope
            const mapInstance = window.map || (typeof map !== 'undefined' ? map : null);
            
            if (mapInstance && mapInstance.on) {
                mapInstance.on('popupopen', (e) => {
                    const popup = e.popup;
                    if (!popup) return;
                    
                    // Get popup container
                    const popupContainer = popup._container;
                    if (!popupContainer) return;
                    
                    // Find popup content wrapper
                    const contentWrapper = popupContainer.querySelector('.leaflet-popup-content-wrapper');
                    if (!contentWrapper) return;
                    
                    // Check if blossoms already exist
                    if (contentWrapper.querySelector('.popup-blossom-container')) return;
                    
                    // Tạo nút X đóng popup - màu vàng ánh kim
                    const closeBtn = document.createElement('div');
                    closeBtn.className = 'popup-close-btn';
                    closeBtn.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M18 6L6 18M6 6l12 12"/>
                        </svg>
                    `;
                    closeBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        mapInstance.closePopup();
                    });
                    contentWrapper.appendChild(closeBtn);
                    
                    // Create blossom container
                    const blossomContainer = document.createElement('div');
                    blossomContainer.className = 'popup-blossom-container';
                    
                    // Create 6-8 falling petals inside popup
                    const petalCount = 7;
                    for (let i = 0; i < petalCount; i++) {
                        const petal = document.createElement('div');
                        petal.className = 'popup-petal';
                        const size = 16 + Math.random() * 8; // 16-24px
                        petal.style.width = `${size}px`;
                        petal.style.height = `${size}px`;
                        petal.style.left = `${Math.random() * 100}%`;
                        petal.style.animationDelay = `${Math.random() * 3}s`;
                        petal.style.animationDuration = `${4 + Math.random() * 2}s`;
                        blossomContainer.appendChild(petal);
                    }
                    
                    // Insert at the beginning of content wrapper (below close button)
                    contentWrapper.insertBefore(blossomContainer, contentWrapper.firstChild);
                });
            } else {
                // Retry after a short delay if map not ready
                setTimeout(checkMapAndSetup, 200);
            }
        };
        
        // Start checking after DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', checkMapAndSetup);
        } else {
            setTimeout(checkMapAndSetup, 500);
        }
    }
    
    /**
     * Create falling blossoms inside Sidebar and static Yellow Apricot flowers
     */
    createSidebarBlossoms() {
        setTimeout(() => {
            const sidebar = document.querySelector('.tet-drawer-side .menu');
            if (!sidebar) return;
            
            const blossomContainer = document.createElement('div');
            blossomContainer.className = 'sidebar-blossom-container';
            blossomContainer.style.position = 'absolute';
            blossomContainer.style.top = '0';
            blossomContainer.style.left = '0';
            blossomContainer.style.width = '100%';
            blossomContainer.style.height = '100%';
            blossomContainer.style.pointerEvents = 'none';
            blossomContainer.style.zIndex = '200';
            blossomContainer.style.overflow = 'hidden';
            blossomContainer.style.opacity = '0.5';
            
            // FIXED: Tạo 20 hoa với vị trí và timing đa dạng
            for (let i = 0; i < 20; i++) {
                const petal = document.createElement('div');
                petal.className = 'sidebar-petal';
                petal.style.position = 'absolute';
                petal.style.width = '12px';
                petal.style.height = '14px';
                petal.style.background = 'linear-gradient(135deg, #FFD700 0%, #FFA500 100%)';
                petal.style.borderRadius = '50% 50% 50% 50% / 60% 60% 40% 40%';
                
                // FIXED: Phân bố đều trên toàn bộ chiều ngang
                petal.style.left = `${(i * 5) % 100}%`;
                
                // FIXED: Delay ngẫu nhiên từ 0-30s để hoa rơi liên tục
                petal.style.animationDelay = `${Math.random() * 30}s`;
                
                // FIXED: Thời gian rơi từ 20-35s (chậm và mượt)
                petal.style.animationDuration = `${20 + Math.random() * 15}s`;
                
                petal.style.opacity = '0.9';
                blossomContainer.appendChild(petal);
            }
            
            sidebar.appendChild(blossomContainer);
            
            // Create static Yellow Apricot flowers (Hoa Mai) as accents
            const flowerContainer = document.createElement('div');
            flowerContainer.className = 'sidebar-mai-flowers';
            flowerContainer.style.position = 'absolute';
            flowerContainer.style.top = '0';
            flowerContainer.style.left = '0';
            flowerContainer.style.width = '100%';
            flowerContainer.style.height = '100%';
            flowerContainer.style.pointerEvents = 'none';
            flowerContainer.style.zIndex = '150'; // Above background, below falling petals
            
            // Place 10 static flowers randomly in sidebar (tăng từ 6)
            const flowerCount = 10;
            for (let i = 0; i < flowerCount; i++) {
                const flower = document.createElement('div');
                flower.className = 'sidebar-mai-flower';
                flower.style.position = 'absolute';
                flower.style.width = `${16 + Math.random() * 8}px`; // 16-24px
                flower.style.height = flower.style.width;
                flower.style.top = `${10 + Math.random() * 80}%`;
                flower.style.left = `${5 + Math.random() * 90}%`;
                flower.style.transform = `rotate(${Math.random() * 360}deg)`;
                flower.style.opacity = '0.6';
                flower.style.filter = 'drop-shadow(0 2px 4px rgba(255, 215, 0, 0.4))';
                flowerContainer.appendChild(flower);
            }
            
            sidebar.appendChild(flowerContainer);
        }, 500);
    }
    
    /**
     * Create festive greeting header
     */
    createGreetingHeader() {
        const header = document.createElement('div');
        header.className = 'tet-greeting-header';
        // Header text without horse icon/emoji
        header.innerHTML = '<h2>Chúc Mừng Năm Mới 2026 - Bính Ngọ</h2>';
        
        // Thêm container cho hiệu ứng hoa rơi (giống border)
        const blossomContainer = document.createElement('div');
        blossomContainer.className = 'greeting-blossom-container';
        blossomContainer.style.position = 'absolute';
        blossomContainer.style.top = '0';
        blossomContainer.style.left = '0';
        blossomContainer.style.width = '100%';
        blossomContainer.style.height = '100%';
        blossomContainer.style.pointerEvents = 'none';
        blossomContainer.style.zIndex = '1';
        blossomContainer.style.overflow = 'hidden';
        
        // Tạo 5-7 hoa mai vàng rơi (giống border)
        const flowerCount = 6;
        for (let i = 0; i < flowerCount; i++) {
            const flower = document.createElement('div');
            flower.className = 'greeting-mai-flower';
            const size = 16 + Math.random() * 8; // 16-24px
            flower.style.width = `${size}px`;
            flower.style.height = `${size}px`;
            flower.style.position = 'absolute';
            flower.style.left = `${Math.random() * 100}%`;
            flower.style.animationDelay = `${Math.random() * 3}s`;
            flower.style.animationDuration = `${4 + Math.random() * 2}s`; // 4-6s
            flower.style.opacity = '0.7';
            flower.style.backgroundImage = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='greetingMaiGrad${i}' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' style='stop-color:%23FFD700;stop-opacity:1' /%3E%3Cstop offset='100%25' style='stop-color:%23FFA500;stop-opacity:1' /%3E%3C/linearGradient%3E%3C/defs%3E%3Cpath d='M50 20 L55 40 L75 40 L60 52 L65 72 L50 60 L35 72 L40 52 L25 40 L45 40 Z' fill='url(%23greetingMaiGrad${i})' stroke='%23FF8C00' stroke-width='1.5'/%3E%3Ccircle cx='50' cy='50' r='3' fill='%23FF8C00'/%3E%3C/svg%3E")`;
            flower.style.backgroundSize = 'contain';
            flower.style.backgroundRepeat = 'no-repeat';
            flower.style.backgroundPosition = 'center';
            flower.style.filter = 'drop-shadow(0 2px 4px rgba(255, 215, 0, 0.8))';
            const rotation = Math.random() * 360;
            flower.style.setProperty('--rotation', `${rotation}deg`);
            blossomContainer.appendChild(flower);
        }
        
        header.appendChild(blossomContainer);
        document.body.appendChild(header);
    }
    
    /**
     * Create fireworks canvas
     */
    createFireworksCanvas() {
        this.fireworksCanvas = document.createElement('canvas');
        this.fireworksCanvas.id = 'fireworks-canvas';
        this.fireworksCanvas.style.position = 'fixed';
        this.fireworksCanvas.style.top = '0';
        this.fireworksCanvas.style.left = '0';
        this.fireworksCanvas.style.width = '100%';
        this.fireworksCanvas.style.height = '100%';
        this.fireworksCanvas.style.zIndex = '998';
        this.fireworksCanvas.style.pointerEvents = 'none';
        document.body.appendChild(this.fireworksCanvas);
        
        this.fireworksCtx = this.fireworksCanvas.getContext('2d');
        this.resizeFireworksCanvas();
        
        window.addEventListener('resize', () => this.resizeFireworksCanvas());
    }
    
    resizeFireworksCanvas() {
        if (this.fireworksCanvas) {
            this.fireworksCanvas.width = window.innerWidth;
            this.fireworksCanvas.height = window.innerHeight;
        }
    }
    
    /**
     * Trigger fireworks celebration
     */
    triggerFireworks(x, y) {
        const colors = ['#FFD700', '#FF0000', '#FFB7C5', '#FFE135', '#FFFFFF'];
        const numFireworks = 3;
        
        for (let i = 0; i < numFireworks; i++) {
            setTimeout(() => {
                const offsetX = (Math.random() - 0.5) * 200;
                const offsetY = (Math.random() - 0.5) * 200;
                this.createFirework(x + offsetX, y + offsetY, colors);
            }, i * 300);
        }
    }
    
    createFirework(x, y, colors) {
        const particles = 50;
        const particlesArray = [];
        
        for (let i = 0; i < particles; i++) {
            const angle = (Math.PI * 2 * i) / particles;
            const speed = Math.random() * 5 + 2;
            const color = colors[Math.floor(Math.random() * colors.length)];
            
            particlesArray.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                color: color,
                life: 1.0,
                decay: Math.random() * 0.02 + 0.01
            });
        }
        
        const animate = () => {
            this.fireworksCtx.clearRect(0, 0, this.fireworksCanvas.width, this.fireworksCanvas.height);
            
            let allDead = true;
            
            for (let particle of particlesArray) {
                if (particle.life > 0) {
                    allDead = false;
                    
                    particle.x += particle.vx;
                    particle.y += particle.vy;
                    particle.vy += 0.1; // Gravity
                    particle.life -= particle.decay;
                    
                    this.fireworksCtx.save();
                    this.fireworksCtx.globalAlpha = particle.life;
                    this.fireworksCtx.fillStyle = particle.color;
                    this.fireworksCtx.beginPath();
                    this.fireworksCtx.arc(particle.x, particle.y, 3, 0, Math.PI * 2);
                    this.fireworksCtx.fill();
                    this.fireworksCtx.restore();
                }
            }
            
            if (!allDead) {
                requestAnimationFrame(animate);
            } else {
                // Clear canvas after animation
                this.fireworksCtx.clearRect(0, 0, this.fireworksCanvas.width, this.fireworksCanvas.height);
            }
        };
        
        animate();
    }
    
    /**
     * Create countdown timer to Lunar New Year 2026
     */
    createCountdown() {
        const countdownDiv = document.createElement('div');
        countdownDiv.className = 'tet-countdown';
        countdownDiv.innerHTML = `
            <h4>🎊 Tết Bính Ngọ 2026 🎊</h4>
            <div class="countdown-time" id="countdown-time">Calculating...</div>
        `;
        document.body.appendChild(countdownDiv);
        
        this.updateCountdown();
        this.countdownTimer = setInterval(() => this.updateCountdown(), 1000);
    }
    
    updateCountdown() {
        const now = new Date();
        const diff = this.tetDate - now;
        
        if (diff <= 0) {
            document.getElementById('countdown-time').textContent = '🎉 Đã đến Tết! 🎉';
            if (this.countdownTimer) {
                clearInterval(this.countdownTimer);
            }
            return;
        }
        
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        
        document.getElementById('countdown-time').textContent = 
            `${days}d ${hours}h ${minutes}m ${seconds}s`;
    }
    
    /**
     * Show greeting toast on first load
     */
    showGreetingToast() {
        if (this.toastShown) return;
        
        const toast = document.createElement('div');
        toast.className = 'tet-toast';
        toast.textContent = 'Chúc Mừng Năm Mới 2026';
        document.body.appendChild(toast);
        
        this.toastShown = true;
        
        // Remove toast after animation
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 4000);
    }
    
    /**
     * High-performance blossom animation using Canvas
     */
    startBlossomAnimation() {
        // Initialize petals
        for (let i = 0; i < this.maxPetals; i++) {
            this.petals.push(this.createPetal());
        }
        
        // Start animation loop
        this.animate();
    }
    
    createPetal() {
        const colors = ['#FFB7C5', '#FFE135', '#FFC0CB', '#FFB6C1']; // Cherry blossom colors
        const color = colors[Math.floor(Math.random() * colors.length)];
        
        // Initialize sway parameters for sine wave motion
        const swayAmplitude = Math.random() * 30 + 20; // 20-50px horizontal sway
        const swayFrequency = Math.random() * 0.02 + 0.01; // Frequency of sway
        const initialSwayPhase = Math.random() * Math.PI * 2; // Random starting phase
        
        return {
            x: Math.random() * this.canvas.width,
            y: Math.random() * -200 - 100, // Start above screen
            size: Math.random() * 8 + 4,
            speed: Math.random() * 0.3 + 0.2, // Slow falling: 0.2-0.5 px/frame (was 1-3)
            rotation: Math.random() * Math.PI * 2,
            rotationSpeed: (Math.random() - 0.5) * 0.15, // Faster rotation
            rotationX: Math.random() * Math.PI * 2, // 3D rotation X axis
            rotationY: Math.random() * Math.PI * 2, // 3D rotation Y axis
            rotationZ: Math.random() * Math.PI * 2, // 3D rotation Z axis
            rotationXSpeed: (Math.random() - 0.5) * 0.05,
            rotationYSpeed: (Math.random() - 0.5) * 0.05,
            rotationZSpeed: (Math.random() - 0.5) * 0.1,
            color: color,
            opacity: Math.random() * 0.3 + 0.7, // 0.7 to 1.0 opacity
            swayAmplitude: swayAmplitude,
            swayFrequency: swayFrequency,
            swayPhase: initialSwayPhase,
            baseX: Math.random() * this.canvas.width // Base X position for sway calculation
        };
    }
    
    animate() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Update and draw petals
        for (let i = 0; i < this.petals.length; i++) {
            const petal = this.petals[i];
            
            // Update vertical position (falling)
            petal.y += petal.speed;
            
            // Update swaying motion using sine wave (wind effect)
            petal.swayPhase += petal.swayFrequency;
            const swayOffset = Math.sin(petal.swayPhase) * petal.swayAmplitude;
            petal.x = petal.baseX + swayOffset;
            
            // Update 3D rotations
            petal.rotation += petal.rotationSpeed;
            petal.rotationX += petal.rotationXSpeed;
            petal.rotationY += petal.rotationYSpeed;
            petal.rotationZ += petal.rotationZSpeed;
            
            // Reset if off screen (fallen past bottom)
            if (petal.y > this.canvas.height + 50) {
                petal.y = -50;
                petal.x = Math.random() * this.canvas.width;
                petal.baseX = petal.x;
                petal.swayPhase = Math.random() * Math.PI * 2; // Reset sway phase
            }
            
            // Draw petal with 3D rotation effect
            this.drawPetal(petal);
        }
        
        // Continue animation
        this.animationId = requestAnimationFrame(() => this.animate());
    }
    
    drawPetal(petal) {
        this.ctx.save();
        this.ctx.translate(petal.x, petal.y);
        
        // Apply 3D rotation effect (simulated with perspective distortion)
        const perspective = 1000;
        const scaleX = 1 + Math.sin(petal.rotationX) * 0.3; // Simulate X rotation
        const scaleY = 1 + Math.cos(petal.rotationY) * 0.3; // Simulate Y rotation
        
        this.ctx.scale(scaleX, scaleY);
        this.ctx.rotate(petal.rotation + petal.rotationZ);
        
        this.ctx.globalAlpha = petal.opacity;
        
        // Draw cherry blossom petal shape (5-petal flower shape)
        this.ctx.beginPath();
        const petalCount = 5;
        const centerRadius = petal.size * 0.3;
        
        for (let i = 0; i < petalCount; i++) {
            const angle = (Math.PI * 2 * i) / petalCount;
            const x = Math.cos(angle) * petal.size;
            const y = Math.sin(angle) * petal.size;
            
            if (i === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        }
        this.ctx.closePath();
        
        // Fill with gradient for depth
        const gradient = this.ctx.createRadialGradient(0, 0, 0, 0, 0, petal.size);
        gradient.addColorStop(0, petal.color);
        gradient.addColorStop(1, this.lightenColor(petal.color, 0.3));
        
        this.ctx.fillStyle = gradient;
        this.ctx.fill();
        
        // Add subtle stroke for definition
        this.ctx.strokeStyle = this.lightenColor(petal.color, 0.2);
        this.ctx.lineWidth = 0.5;
        this.ctx.stroke();
        
        // Draw center stamen
        this.ctx.beginPath();
        this.ctx.arc(0, 0, centerRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = '#FF8C00';
        this.ctx.fill();
        
        this.ctx.restore();
    }
    
    /**
     * Helper: Lighten a color
     */
    lightenColor(color, amount) {
        // Simple color lightening (for gradient effect)
        if (color.startsWith('#')) {
            const num = parseInt(color.replace('#', ''), 16);
            const r = Math.min(255, ((num >> 16) & 0xff) + Math.floor(255 * amount));
            const g = Math.min(255, ((num >> 8) & 0xff) + Math.floor(255 * amount));
            const b = Math.min(255, (num & 0xff) + Math.floor(255 * amount));
            return `rgb(${r}, ${g}, ${b})`;
        }
        return color;
    }
    
    /**
     * Apply Tết theme to route line
     */
    styleRouteLine(polyline) {
        if (polyline && polyline.setStyle) {
            polyline.setStyle({
                color: '#FFD700', // --tet-gold
                weight: 5,
                opacity: 0.9
            });
            
            // Add CSS class for glow effect
            if (polyline._path) {
                polyline._path.classList.add('tet-route-line');
            }
        }
    }
    
    /**
     * Create custom festive markers with SVG
     */
    createFestiveMarker(type, latlng) {
        let svgContent;
        
        if (type === 'start') {
            // Li Xi (Red Envelope) SVG
            svgContent = `
                <svg viewBox="0 0 100 120" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <linearGradient id="envelopeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:#D80000;stop-opacity:1" />
                            <stop offset="100%" style="stop-color:#A00000;stop-opacity:1" />
                        </linearGradient>
                    </defs>
                    <!-- Envelope body -->
                    <rect x="20" y="30" width="60" height="70" rx="5" fill="url(#envelopeGrad)" stroke="#FFD700" stroke-width="2"/>
                    <!-- Envelope flap -->
                    <path d="M 20 30 L 50 50 L 80 30 Z" fill="#FF0000" stroke="#FFD700" stroke-width="2"/>
                    <!-- Gold decoration -->
                    <circle cx="50" cy="65" r="8" fill="#FFD700" opacity="0.8"/>
                    <text x="50" y="70" font-size="12" fill="#D80000" text-anchor="middle" font-weight="bold">福</text>
                </svg>
            `;
        } else {
            // Golden Horse Coin SVG
            svgContent = `
                <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <linearGradient id="coinGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:#FFD700;stop-opacity:1" />
                            <stop offset="100%" style="stop-color:#FFA500;stop-opacity:1" />
                        </linearGradient>
                        <radialGradient id="coinShine" cx="30%" cy="30%">
                            <stop offset="0%" style="stop-color:#FFFFFF;stop-opacity:0.8" />
                            <stop offset="100%" style="stop-color:#FFD700;stop-opacity:0" />
                        </radialGradient>
                    </defs>
                    <!-- Coin circle -->
                    <circle cx="50" cy="50" r="45" fill="url(#coinGrad)" stroke="#D80000" stroke-width="3"/>
                    <circle cx="50" cy="50" r="45" fill="url(#coinShine)"/>
                    <!-- Horse silhouette -->
                    <path d="M 30 50 Q 25 40 35 35 Q 45 30 55 35 Q 65 40 70 50 Q 65 60 55 65 Q 45 70 35 65 Q 25 60 30 50 Z" 
                          fill="#D80000" 
                          opacity="0.9"/>
                    <!-- Chinese character for horse -->
                    <text x="50" y="60" font-size="20" fill="#FFD700" text-anchor="middle" font-weight="bold">馬</text>
                </svg>
            `;
        }
        
        return L.divIcon({
            html: `<div class="tet-marker-svg">${svgContent}</div>`,
            className: `tet-marker-${type}`,
            iconSize: [40, 40],
            iconAnchor: [20, 40],
            popupAnchor: [0, -40]
        });
    }
    
    /**
     * Trigger fireworks when route is calculated
     * @param {Object} routeCenter - Leaflet LatLng object with lat and lng properties
     * @param {Object} map - Leaflet map instance (optional, for accurate coordinate conversion)
     */
    onRouteCalculated(routeCenter, map = null) {
        if (!routeCenter) return;
        
        let screenX, screenY;
        
        if (map && typeof map.latLngToContainerPoint === 'function' && routeCenter.lat && routeCenter.lng) {
            // Convert lat/lng to screen coordinates using Leaflet (chính xác nhất)
            try {
                const containerPoint = map.latLngToContainerPoint(routeCenter);
                screenX = containerPoint.x;
                screenY = containerPoint.y;
            } catch (e) {
                // Fallback nếu có lỗi
                screenX = window.innerWidth / 2;
                screenY = window.innerHeight / 2;
            }
        } else {
            // Fallback: center of screen
            screenX = window.innerWidth / 2;
            screenY = window.innerHeight / 2;
        }
        
        this.triggerFireworks(screenX, screenY);
    }
    
    /**
     * Cleanup method
     */
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
        }
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
        if (this.fireworksCanvas && this.fireworksCanvas.parentNode) {
            this.fireworksCanvas.parentNode.removeChild(this.fireworksCanvas);
        }
    }
}

// Export TetTheme class globally
if (typeof window !== 'undefined') {
    window.TetTheme = TetTheme;
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TetTheme;
}

