"""
RedByte Loading Splash Screen with Animated Rotor Spin
"""
from PyQt6.QtWidgets import QSplashScreen, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QFont, QTransform
import math


class RotorSplashScreen(QSplashScreen):
    """Premium loading splash with animated rotor and branding"""
    
    def __init__(self):
        # Create pixmap for splash
        pixmap = QPixmap(600, 400)
        pixmap.fill(QColor(10, 14, 26))
        super().__init__(pixmap)
        
        self.rotor_angle = 0
        self.loading_dots = 0
        
        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._animate)
        self.timer.start(30)  # ~33 FPS
        
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    
    def _animate(self):
        """Animate rotor rotation and loading text"""
        self.rotor_angle = (self.rotor_angle + 3) % 360
        self.loading_dots = (self.loading_dots + 1) % 60
        self.repaint()
    
    def drawContents(self, painter):
        """Draw animated splash content"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background gradient
        from PyQt6.QtGui import QLinearGradient
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(10, 14, 26))
        gradient.setColorAt(0.5, QColor(15, 20, 33))
        gradient.setColorAt(1, QColor(20, 29, 47))
        painter.fillRect(self.rect(), gradient)
        
        # Draw border
        border_pen = QPen(QColor(16, 185, 129), 3)
        painter.setPen(border_pen)
        painter.drawRect(2, 2, self.width() - 4, self.height() - 4)
        
        # === RedByte Branding ===
        font_title = QFont("JetBrains Mono", 36, QFont.Weight.Bold)
        painter.setFont(font_title)
        painter.setPen(QColor(16, 185, 129))
        painter.drawText(self.rect().adjusted(0, 50, 0, 0), Qt.AlignmentFlag.AlignHCenter, "RedByte")
        
        font_subtitle = QFont("JetBrains Mono", 14, QFont.Weight.Normal)
        painter.setFont(font_subtitle)
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(self.rect().adjusted(0, 100, 0, 0), Qt.AlignmentFlag.AlignHCenter, "HIL Verifier Suite")
        
        # === Animated Rotor ===
        center_x = self.width() // 2
        center_y = self.height() // 2 + 20
        rotor_radius = 60
        
        # Save painter state
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self.rotor_angle)
        
        # Draw rotor shaft (center circle)
        painter.setPen(QPen(QColor(59, 130, 246, 200), 2))
        painter.setBrush(QColor(30, 41, 59, 220))
        painter.drawEllipse(-10, -10, 20, 20)
        
        # Draw rotor blades (3-phase representation)
        blade_colors = [
            QColor(250, 204, 21, 200),  # Yellow (Phase A)
            QColor(34, 197, 94, 200),    # Green (Phase B)
            QColor(236, 72, 153, 200),   # Magenta (Phase C)
        ]
        
        for i, color in enumerate(blade_colors):
            angle_offset = i * 120
            blade_x = rotor_radius * math.cos(math.radians(angle_offset))
            blade_y = rotor_radius * math.sin(math.radians(angle_offset))
            
            # Draw blade arm
            pen = QPen(color, 8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(0, 0, int(blade_x), int(blade_y))
            
            # Draw blade tip circle
            painter.setBrush(color)
            painter.drawEllipse(int(blade_x - 8), int(blade_y - 8), 16, 16)
        
        # Restore painter state
        painter.restore()
        
        # === Loading Text with Animated Dots ===
        dot_count = (self.loading_dots // 15) + 1  # Cycle through 1-4 dots
        dots = "." * dot_count
        loading_text = f"Booting RedByte Systems{dots}"
        
        font_loading = QFont("JetBrains Mono", 11, QFont.Weight.Normal)
        painter.setFont(font_loading)
        painter.setPen(QColor(100, 116, 139))
        painter.drawText(self.rect().adjusted(0, 0, 0, -30), 
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, 
                        loading_text)
        
        # === Neon Glow Ring ===
        glow_alpha = int(80 + 40 * math.sin(math.radians(self.rotor_angle * 2)))
        glow_pen = QPen(QColor(16, 185, 129, glow_alpha), 3)
        painter.setPen(glow_pen)
        painter.drawEllipse(center_x - rotor_radius - 15, 
                           center_y - rotor_radius - 15, 
                           (rotor_radius + 15) * 2, 
                           (rotor_radius + 15) * 2)
    
    def finish_animation(self, window):
        """Finish animation and close splash"""
        self.timer.stop()
        self.finish(window)
