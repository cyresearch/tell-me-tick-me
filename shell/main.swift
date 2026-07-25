// tellmetickme 悬浮壳: QQ 式可拖动 + 边缘磁吸小窗
// 行为:
//   - 抓住把手(那条带三个点的竖条)可自由拖动窗口到屏幕任意位置
//   - 松手时靠近左/右屏幕边(阈值内)会磁吸贴边; 不靠边则浮在原地
//   - 贴边后: 鼠标碰边滑出、离开 0.6 秒收回 (QQ 隐藏效果); 浮在中间则常驻不收
//   - 置顶+全空间可见; 点击不抢焦点, 勾待办不切走当前 app
//   - 菜单栏 ✓: 固定展开 / 刷新 / 浏览器打开 / 退出
// 编译: ./build.sh   环境变量: DESK_URL / DESK_WIDTH / DESK_START_EXPANDED

import AppKit
import WebKit

let env = ProcessInfo.processInfo.environment
let PAGE_URL = env["DESK_URL"] ?? "http://127.0.0.1:8765"
let PANEL_W: CGFloat = CGFloat(Double(env["DESK_WIDTH"] ?? "") ?? 380)
let HEIGHT_RATIO: CGFloat = 0.82
let HANDLE_W: CGFloat = 12         // 把手条宽度(也是收回时露出的宽度)
let TOPBAR_H: CGFloat = 22         // 顶部拖动条高度(第二个抓手, 把手被挡也能拖)
let TRIGGER_PAD: CGFloat = 3       // 屏幕边触发带比把手略宽, 好碰
let SNAP: CGFloat = 24             // 松手时离边多近就磁吸(要"怼到边上"才吸, 中间随便放)
let COLLAPSE_DELAY = 0.6
let ANIM = 0.22

enum Dock: String { case left, right, top, bottom, floating }

final class SlidePanel: NSPanel {
    override var canBecomeKey: Bool { true }
    // 吸顶收回时窗口要移出屏幕上缘, 系统默认会把它按回来, 这里放行
    override func constrainFrameRect(_ frameRect: NSRect, to screen: NSScreen?) -> NSRect {
        frameRect
    }
}

// 把手: 可拖动抓手, 事件转发给 Shell
final class HandleView: NSView {
    var onBegan: (() -> Void)?
    var onDragged: (() -> Void)?
    var onEnded: (() -> Void)?
    override func mouseDown(with e: NSEvent) { onBegan?() }
    override func mouseDragged(with e: NSEvent) { onDragged?() }
    override func mouseUp(with e: NSEvent) { onEnded?() }
    override func resetCursorRects() { addCursorRect(bounds, cursor: .openHand) }
}

final class Shell: NSObject, NSApplicationDelegate, WKNavigationDelegate, NSWindowDelegate {
    var panel: SlidePanel!
    var web: WKWebView!
    var handle: HandleView!
    var topbar: HandleView!
    var dots: [NSView] = []
    var status: NSStatusItem!
    var pinItem: NSMenuItem!
    var dock: Dock = .right
    var expanded = false
    var pinned = false
    var dragging = false
    var dragOffset = NSPoint.zero
    var lastInside = Date()
    // 窗口锚定"自己所在的屏", 不用 NSScreen.main(那是"焦点所在屏", 多屏/随航下
    // 会跟着鼠标点击换屏, 曾把窗口传送到 iPad 上)。完全出屏时退回物理主屏。
    var screenFrame: NSRect {
        ((panel?.screen) ?? NSScreen.screens.first)?.visibleFrame ?? .zero
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        NSApp.setActivationPolicy(.accessory)
        let vf = screenFrame
        let h = vf.height * HEIGHT_RATIO
        let y = vf.minY + (vf.height - h) / 2

        panel = SlidePanel(
            contentRect: NSRect(x: vf.maxX - HANDLE_W, y: y, width: PANEL_W, height: h),
            styleMask: [.borderless, .nonactivatingPanel, .fullSizeContentView, .resizable],
            backing: .buffered, defer: false)
        panel.minSize = NSSize(width: 300, height: 260)   // 拉太小就没法用了
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.becomesKeyOnlyIfNeeded = true

        let root = NSView(frame: NSRect(x: 0, y: 0, width: PANEL_W, height: h))
        root.wantsLayer = true
        root.layer?.cornerRadius = 12
        root.layer?.masksToBounds = true
        root.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor

        web = WKWebView(frame: NSRect(x: HANDLE_W, y: 0, width: PANEL_W - HANDLE_W, height: h),
                        configuration: WKWebViewConfiguration())
        web.navigationDelegate = self
        web.uiDelegate = self
        web.load(URLRequest(url: URL(string: PAGE_URL)!))

        handle = HandleView(frame: NSRect(x: 0, y: 0, width: HANDLE_W, height: h))
        handle.wantsLayer = true
        handle.layer?.backgroundColor = NSColor.tertiaryLabelColor.cgColor
        for _ in 0..<3 {
            let dot = NSView(frame: .zero)
            dot.wantsLayer = true
            dot.layer?.cornerRadius = 1.5
            dot.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
            handle.addSubview(dot)
            dots.append(dot)
        }
        handle.onBegan = { [weak self] in self?.dragBegan() }
        handle.onDragged = { [weak self] in self?.dragMoved() }
        handle.onEnded = { [weak self] in self?.dragEnded() }

        // 顶部拖动条: 第二个抓手, 横贯全宽; 侧把手被挡时靠它拖
        topbar = HandleView(frame: NSRect(x: 0, y: h - TOPBAR_H, width: PANEL_W, height: TOPBAR_H))
        topbar.wantsLayer = true
        topbar.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
        let grip = NSView(frame: NSRect(x: PANEL_W/2 - 18, y: TOPBAR_H/2 - 2, width: 36, height: 4))
        grip.wantsLayer = true
        grip.layer?.cornerRadius = 2
        grip.layer?.backgroundColor = NSColor.tertiaryLabelColor.cgColor
        grip.autoresizingMask = [.minXMargin, .maxXMargin]
        topbar.addSubview(grip)
        topbar.onBegan = { [weak self] in self?.dragBegan() }
        topbar.onDragged = { [weak self] in self?.dragMoved() }
        topbar.onEnded = { [weak self] in self?.dragEnded() }

        root.addSubview(web)
        root.addSubview(handle)
        root.addSubview(topbar)
        panel.contentView = root
        panel.delegate = self
        layoutFor(dock)
        restoreState()
        panel.orderFrontRegardless()

        setupStatusItem()
        setupMainMenu()
        if env["DESK_START_EXPANDED"] == "1" { expand() }
        Timer.scheduledTimer(withTimeInterval: 0.08, repeats: true) { [weak self] _ in self?.tick() }
    }

    // ---- 把手拖动 ----
    func dragBegan() {
        dragging = true
        dragOffset = NSPoint(x: NSEvent.mouseLocation.x - panel.frame.minX,
                             y: NSEvent.mouseLocation.y - panel.frame.minY)
    }
    func dragMoved() {
        let m = NSEvent.mouseLocation
        panel.setFrameOrigin(NSPoint(x: m.x - dragOffset.x, y: m.y - dragOffset.y))
    }
    func dragEnded() {
        dragging = false
        let vf = screenFrame, f = panel.frame
        // 四条边各算距离, 取最近且在磁吸阈值内的那条; 都不够近就浮着
        let gaps: [(Dock, CGFloat)] = [(.right, vf.maxX - f.maxX), (.left, f.minX - vf.minX),
                                       (.top, vf.maxY - f.maxY), (.bottom, f.minY - vf.minY)]
        let near = gaps.filter { $0.1 < SNAP }.min { $0.1 < $1.1 }
        let newDock = near?.0 ?? .floating
        if newDock != dock { dock = newDock; layoutFor(dock) }
        expanded = true
        lastInside = Date()
        animate(to: expandedFrame())
        saveState()
    }

    // 窗口拉伸后重摆内部布局 + 记住新尺寸
    func windowDidResize(_ n: Notification) {
        layoutFor(dock)
        saveState()
    }

    // 尺寸/位置/吸附状态跨重启记忆
    func saveState() {
        let d = UserDefaults.standard
        d.set(NSStringFromRect(panel.frame), forKey: "deskFrame")
        d.set(dock.rawValue, forKey: "deskDock")
    }
    func restoreState() {
        let d = UserDefaults.standard
        if let dk = d.string(forKey: "deskDock"), let dd = Dock(rawValue: dk) { dock = dd }
        if let fs = d.string(forKey: "deskFrame") {
            let f = NSRectFromString(fs)
            if f.width >= 300, f.height >= 260 {
                var r = panel.frame
                r.size = f.size
                if dock == .floating { r.origin = f.origin }
                panel.setFrame(r, display: false)
            }
        }
        layoutFor(dock)
        if dock == .floating {
            panel.setFrame(expandedFrame(), display: false)   // 出界校验顺带做了
            expanded = true
        } else {
            panel.setFrame(collapsedFrame(), display: false)
            expanded = false
        }
    }

    // 抓手布局: 顶栏永远在窗口顶部; 侧把手随 dock 换边; 吸底时露出的就是顶栏, 侧把手藏起
    func layoutFor(_ d: Dock) {
        let w = panel.frame.width, h = panel.frame.height
        let all: CACornerMask = [.layerMinXMinYCorner, .layerMinXMaxYCorner,
                                 .layerMaxXMinYCorner, .layerMaxXMaxYCorner]
        topbar.frame = NSRect(x: 0, y: h - TOPBAR_H, width: w, height: TOPBAR_H)
        handle.isHidden = (d == .bottom)
        switch d {
        case .left:
            handle.frame = NSRect(x: w - HANDLE_W, y: 0, width: HANDLE_W, height: h - TOPBAR_H)
            web.frame = NSRect(x: 0, y: 0, width: w - HANDLE_W, height: h - TOPBAR_H)
            panel.contentView?.layer?.maskedCorners = [.layerMaxXMinYCorner, .layerMaxXMaxYCorner]
        case .right, .floating:
            handle.frame = NSRect(x: 0, y: 0, width: HANDLE_W, height: h - TOPBAR_H)
            web.frame = NSRect(x: HANDLE_W, y: 0, width: w - HANDLE_W, height: h - TOPBAR_H)
            panel.contentView?.layer?.maskedCorners =
                d == .floating ? all : [.layerMinXMinYCorner, .layerMinXMaxYCorner]
        case .top:                                    // 吸顶, 收回后露窗口底缘的横把手
            handle.frame = NSRect(x: 0, y: 0, width: w, height: HANDLE_W)
            web.frame = NSRect(x: 0, y: HANDLE_W, width: w, height: h - HANDLE_W - TOPBAR_H)
            panel.contentView?.layer?.maskedCorners = [.layerMinXMinYCorner, .layerMaxXMinYCorner]
        case .bottom:                                 // 吸底, 收回后露的就是顶栏(自带抓手)
            web.frame = NSRect(x: 0, y: 0, width: w, height: h - TOPBAR_H)
            panel.contentView?.layer?.maskedCorners = [.layerMinXMaxYCorner, .layerMaxXMaxYCorner]
        }
        layoutDots(d)
    }

    func layoutDots(_ d: Dock) {
        let hf = handle.frame
        let horizontal = (d == .top || d == .bottom)
        for (i, dot) in dots.enumerated() {
            let off = CGFloat(i - 1) * 12
            dot.frame = horizontal
                ? NSRect(x: hf.width/2 - 1.5 + off, y: hf.height/2 - 1.5, width: 3, height: 3)
                : NSRect(x: hf.width/2 - 1.5, y: hf.height/2 - 1.5 + off, width: 3, height: 3)
        }
    }

    // ---- 展开位 / 收回位 ----
    func expandedFrame() -> NSRect {
        let vf = screenFrame, f = panel.frame
        var r = f
        switch dock {
        case .left:  r.origin.x = vf.minX
        case .right: r.origin.x = vf.maxX - f.width
        case .top:   r.origin.y = vf.maxY - f.height
        case .bottom: r.origin.y = vf.minY
        case .floating: break
        }
        // 贴左右时纵向收回屏幕内, 贴上下时横向收回屏幕内
        if dock == .left || dock == .right {
            r.origin.y = max(vf.minY, min(r.origin.y, vf.maxY - f.height))
        } else if dock == .top || dock == .bottom {
            r.origin.x = max(vf.minX, min(r.origin.x, vf.maxX - f.width))
        } else {
            // 兜底二: 浮动态整窗不出屏顶(顶栏永远可见), 底部最多沉到只剩顶部 60px,
            // 横向至少露 80px — 放哪就停哪, 只在真出界时拉回
            r.origin.y = max(vf.minY + 60 - r.height, min(r.origin.y, vf.maxY - r.height))
            r.origin.x = max(vf.minX - r.width + 80, min(r.origin.x, vf.maxX - 80))
        }
        return r
    }
    func collapsedFrame() -> NSRect {
        let vf = screenFrame
        var r = expandedFrame()
        switch dock {
        case .left:   r.origin.x = vf.minX - r.width + HANDLE_W
        case .right:  r.origin.x = vf.maxX - HANDLE_W
        case .top:    r.origin.y = vf.maxY - HANDLE_W
        case .bottom: r.origin.y = vf.minY - r.height + TOPBAR_H   // 露出的是顶栏
        case .floating: break
        }
        return r
    }

    // 兜底一: 一键复位(菜单「把窗口叫回来」) — 回到吸右展开、纵向居中
    @objc func resetPosition() {
        dock = .right
        layoutFor(dock)
        expanded = true
        pinned = false
        pinItem.state = .off
        lastInside = Date()
        let vf = screenFrame
        let f = panel.frame                       // 尺寸保留, 只复位位置
        animate(to: NSRect(x: vf.maxX - f.width, y: vf.minY + (vf.height - f.height) / 2,
                           width: f.width, height: f.height))
        panel.orderFrontRegardless()
        saveState()
    }

    var autoCollapses: Bool { expanded && !pinned && !dragging && dock != .floating }

    func tick() {
        if dragging { return }
        let m = NSEvent.mouseLocation, f = panel.frame, vf = screenFrame
        // 兜底三: 窗口彻底出屏(任何原因)就自动叫回来
        if f.intersection(vf).isEmpty { resetPosition(); return }
        if expanded {
            guard autoCollapses else { return }
            if f.insetBy(dx: -24, dy: -24).contains(m) {
                lastInside = Date()
            } else if Date().timeIntervalSince(lastInside) > COLLAPSE_DELAY {
                collapse()
            }
        } else {
            let onBand: Bool
            switch dock {
            case .left:   onBand = m.x <= vf.minX + HANDLE_W + TRIGGER_PAD
                              && m.y >= f.minY && m.y <= f.maxY
            case .right:  onBand = m.x >= vf.maxX - HANDLE_W - TRIGGER_PAD
                              && m.y >= f.minY && m.y <= f.maxY
            case .top:    onBand = m.y >= vf.maxY - HANDLE_W - TRIGGER_PAD && m.y <= vf.maxY
                              && m.x >= f.minX && m.x <= f.maxX
            case .bottom: onBand = m.y <= vf.minY + TOPBAR_H + TRIGGER_PAD
                              && m.x >= f.minX && m.x <= f.maxX
            case .floating: onBand = false
            }
            if onBand { expand() }
        }
    }

    func expand() { guard !expanded else { return }; expanded = true; lastInside = Date()
        animate(to: expandedFrame()) }
    func collapse() { guard expanded else { return }; expanded = false
        animate(to: collapsedFrame()) }
    func animate(to f: NSRect) {
        NSAnimationContext.runAnimationGroup { ctx in
            ctx.duration = ANIM
            ctx.timingFunction = CAMediaTimingFunction(name: .easeOut)
            panel.animator().setFrame(f, display: true)
        }
    }

    // ---- 菜单栏 ----
    func setupStatusItem() {
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        status.button?.title = "✓"
        let menu = NSMenu()
        pinItem = NSMenuItem(title: "固定展开", action: #selector(togglePin), keyEquivalent: "p")
        pinItem.target = self; menu.addItem(pinItem)
        let home = NSMenuItem(title: "把窗口叫回来", action: #selector(resetPosition), keyEquivalent: "h")
        home.target = self; menu.addItem(home)
        let r = NSMenuItem(title: "刷新页面", action: #selector(reloadPage), keyEquivalent: "r")
        r.target = self; menu.addItem(r)
        let b = NSMenuItem(title: "在浏览器打开", action: #selector(openBrowser), keyEquivalent: "o")
        b.target = self; menu.addItem(b)
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "退出悬浮窗", action: #selector(NSApplication.terminate(_:)),
                                keyEquivalent: "q"))
        status.menu = menu
    }
    // 无菜单栏的 app 里 Cmd+C/V 这类快捷键是死的(靠编辑菜单派发);
    // 建一个隐形主菜单, 复制/粘贴/全选/撤销就活了(app 仍不占 Dock 不显菜单栏)
    func setupMainMenu() {
        let main = NSMenu()
        let editItem = NSMenuItem()
        main.addItem(editItem)
        let edit = NSMenu(title: "编辑")
        edit.addItem(withTitle: "撤销", action: Selector(("undo:")), keyEquivalent: "z")
        edit.addItem(withTitle: "重做", action: Selector(("redo:")), keyEquivalent: "Z")
        edit.addItem(.separator())
        edit.addItem(withTitle: "剪切", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "拷贝", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "粘贴", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "全选", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit
        NSApp.mainMenu = main
    }

    @objc func togglePin() { pinned.toggle(); pinItem.state = pinned ? .on : .off; if pinned { expand() } }
    @objc func reloadPage() { web.reload() }
    @objc func openBrowser() { NSWorkspace.shared.open(URL(string: PAGE_URL)!) }

    func webView(_ w: WKWebView, didFailProvisionalNavigation nav: WKNavigation!, withError e: Error) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) { w.reload() }
    }
    func webView(_ w: WKWebView, didFail nav: WKNavigation!, withError e: Error) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) { w.reload() }
    }
}

// 网页里的 alert()/confirm() 弹成原生对话框 (WKWebView 默认静默吞掉)
extension Shell: WKUIDelegate {
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = message; a.runModal(); completionHandler()
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = message
        a.addButton(withTitle: "好"); a.addButton(withTitle: "取消")
        completionHandler(a.runModal() == .alertFirstButtonReturn)
    }
}

let app = NSApplication.shared
let shell = Shell()
app.delegate = shell
app.run()
