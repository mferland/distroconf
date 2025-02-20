;; Look & feel
(setq inhibit-startup-screen t)
;; (set-default-font "DejaVu Sans Mono-9")
(add-to-list 'default-frame-alist '(font . "DejaVu Sans Mono-9"))
(scroll-bar-mode -1)
(menu-bar-mode -1)
(tool-bar-mode -1)
(setq display-time-default-load-average nil)
(setq display-time-day-and-date t
      display-time-24hr-format t)
(display-time)
(transient-mark-mode 1)
(show-paren-mode 1)
(setq-default indicate-buffer-boundaries 'left)
(setq-default indicate-empty-lines +1)
(setq-default indent-tabs-mode nil)

(defun mfe/kill-this-buffer ()
  "Kill the current buffer."
  (interactive)
  (kill-buffer (current-buffer)))

(global-set-key (kbd "C-x k") 'mfe/kill-this-buffer)
(global-set-key (kbd "C-.") 'other-window)
(global-set-key (kbd "M-*") 'pop-tag-mark)
(global-auto-revert-mode t)

;; Always ask before quitting Emacs
(setq confirm-kill-emacs 'y-or-n-p)

;; dired listing using human readable sizes
(setq dired-listing-switches "-alh")

(setenv "SSH_AUTH_SOCK" (concat (getenv "HOME") "/.ssh-auth-sock"))

(require 'package)

;; Add MELPA to package-archives.
(add-to-list 'package-archives
             '("melpa" . "https://melpa.org/packages/") t)

;; initialize built-in package management
(package-initialize)

;; update packages list if we are on a new install
(unless package-archive-contents
  (package-refresh-contents))

;; a list of pkgs to programmatically install
;; ensure installed via package.el
(setq my-package-list '(use-package))

;; programmatically install/ensure installed
;; pkgs in your personal list
(dolist (package my-package-list)
  (unless (package-installed-p package)
    (package-install package)))

(require 'use-package)

;; Theme
(load-theme 'tango-dark t)

;; Global hl
(global-hl-line-mode 1)
(set-face-background 'hl-line "gray12")
(set-face-foreground 'highlight nil)

;; Emacs backup configuration
(setq backup-directory-alist `(("." . "~/.saves")))
(setq backup-by-copying t)
(setq delete-old-versions t
  kept-new-versions 6
  kept-old-versions 2
  version-control t)

(add-to-list 'load-path "~/.emacs.d/site-lisp/bb-mode")
(require 'bb-mode)
(setq auto-mode-alist (cons '("\\.bb$" . bb-mode) auto-mode-alist))
(setq auto-mode-alist (cons '("\\.inc$" . bb-mode) auto-mode-alist))
(setq auto-mode-alist (cons '("\\.bbappend$" . bb-mode) auto-mode-alist))
(setq auto-mode-alist (cons '("\\.bbclass$" . bb-mode) auto-mode-alist))

(add-to-list 'load-path "~/.emacs.d/site-lisp/flex")
(require 'flex)
(add-to-list 'auto-mode-alist '("\\.l$" . flex-mode))
(autoload 'flex-mode "flex")

(add-to-list 'load-path "~/.emacs.d/site-lisp/bison")
(require 'bison)
(add-to-list 'auto-mode-alist '("\\.y$" . bison-mode))
(autoload 'bison-mode "bison")

;; C++ hook
(defun my-c++-mode-hook ()
  (setq c-basic-offset 4)
  (setq-default indent-tabs-mode t)
  (c-set-offset 'substatement-open 0)
  (setq c-default-style "bsd")
  (setq show-trailing-whitespace t)
  (font-lock-add-keywords nil '(("\\<\\(FIXME\\|TODO\\|BUG\\):" 1 font-lock-warning-face t))))
(add-hook 'c++-mode-hook 'my-c++-mode-hook)

;; C hook
(defun my-c-mode-hook ()
  (setq c-basic-offset 8)
  (setq-default indent-tabs-mode t)
  (c-set-offset 'substatement-open 0)
  (setq c-default-style "linux")
  (setq show-trailing-whitespace t)
  (font-lock-add-keywords nil '(("\\<\\(FIXME\\|TODO\\|BUG\\):" 1 font-lock-warning-face t)))
  (setq flycheck-gcc-language-standard "gnu99"))
(add-hook 'c-mode-hook 'my-c-mode-hook)
;;(add-hook 'c-mode-hook #'lsp)

;; Python
(defun my-python-mode-hook ()
  (setq show-trailing-whitespace t)
  (setq python-shell-interpreter "python3"))
(add-hook 'python-mode-hook 'my-python-mode-hook)

;; DTS
(defun my-dts-mode-hook ()
  (setq whitespace-style
   '(face tabs spaces trailing lines space-before-tab newline indentation empty space-after-tab tab-mark))
  (whitespace-mode))
(add-hook 'dts-mode-hook 'my-dts-mode-hook)

;; AUCTex
(setq TeX-auto-save t)
(setq TeX-parse-self t)
(setq-default TeX-master nil)
(add-hook 'LaTeX-mode-hook 'visual-line-mode)
(add-hook 'LaTeX-mode-hook 'flyspell-mode)
(add-hook 'LaTeX-mode-hook 'LaTeX-math-mode)
(add-hook 'LaTeX-mode-hook 'turn-on-reftex)
(setq reftex-plug-into-AUCTeX t)
(setq TeX-PDF-mode t)

(use-package magit
  :ensure t
  :config
  (global-set-key (kbd "C-x g") 'magit-status)
  (with-eval-after-load 'info
    (info-initialize)
    (add-to-list 'Info-directory-list
                 "~/.emacs.d/magit/Documentation/")))

(use-package expand-region
  :ensure t
  :init
  (global-set-key (kbd "C-=") 'er/expand-region))

;; (defun my-org-screenshot ()
;;   "Take a screenshot into a time stamped unique-named file in the
;; same directory as the org-buffer and insert a link to this file."
;;   (interactive)
;;   (setq filename
;;         (concat
;;          (make-temp-name
;;           (concat (buffer-file-name)
;;                   "_"
;;                   (format-time-string "%Y%m%d_%H%M%S_")) ) ".png"))
;;   (call-process "import" nil nil nil filename)
;;   (insert (concat "[[" filename "]]"))
;;   (org-display-inline-images))

(defun mfe/org-screenshot-from-clipboard ()
  "Take screenshot from clipboard, copy it to the same directory
  as the org-buffer and insert a link to this file."
  (interactive)
  (setq filename
	(concat
	 (make-temp-name
	  (concat (buffer-file-name)
		  "_"
		  (format-time-string "%Y%m%d_%H%M%S_")) ) ".png"))
  (message "Saving screenshot to: %s" filename)
  ;; (call-process "xclip" nil  "-selection" "clipboard" "-t" "image/png -o" filename)
  (shell-command-to-string (concat "/usr/bin/xclip -selection clipboard -t image/png -o > " filename))
  (insert (concat "[[" filename "]]"))
  (org-display-inline-images))

(use-package org-roam
  :ensure t
  :init
  (setq org-roam-v2-ack t)
  :custom
  (org-roam-directory "~/notes")
  (org-roam-completion-everywhere t)
  :bind (("C-c n l" . org-roam-buffer-toggle)
         ("C-c n f" . org-roam-node-find)
         ("C-c n i" . org-roam-node-insert)
         :map org-mode-map
         ("C-M-i" . completion-at-point))
  :config
  (org-roam-setup))

(use-package helm
  :ensure t
  :init
  (setq helm-split-window-in-side-p t)
  (setq helm-move-to-line-cycle-in-source t)
  (setq helm-ff-search-library-in-sexp t)
  (setq helm-scroll-amount 8)
  (setq helm-ff-file-name-history-use-recentf t)
  (global-unset-key (kbd "C-x c"))
  :bind (("C-c h"   . helm-command-prefix)
         ("M-x"     . helm-M-x)
         ("C-x b"   . helm-mini)
         ("C-x C-f" . helm-find-files)
         :map helm-map
         ("<tab>" . helm-execute-persistent-action)
         ("C-i"   . helm-execute-persistent-action)
         ("C-z"   . helm-select-action))
  :config
  (helm-mode 1))

(use-package dts-mode
  :ensure t)

(use-package powerline
  :ensure t
  :config
  (powerline-default-theme))

(use-package yaml-mode
  :ensure t
  :config
  (add-to-list 'auto-mode-alist '("\\.yml\\'" . yaml-mode))
  (add-to-list 'auto-mode-alist '("\\.yaml\\'" . yaml-mode)))

(use-package cmake-mode
  :ensure t)

(use-package systemd
  :ensure t)

(use-package dockerfile-mode
  :ensure t)

(use-package w3m
  :ensure t)

(use-package kconfig-mode
  :ensure t)

(use-package langtool
  :ensure t
  :init
  (setq langtool-http-server-host "localhost")
  (setq langtool-http-server-port 8010))

(use-package markdown-mode
  :ensure t
  :mode ("README\\.md\\'" . gfm-mode)
  :init (setq markdown-command "multimarkdown"))

(use-package php-mode
  :ensure t)

(use-package web-mode
  :ensure t)

(use-package company
  :ensure t)

(use-package rtags-xref
  :ensure t
  :init (setq xref-prompt-for-identifier nil))
(add-hook 'c-mode-common-hook #'rtags-xref-enable)

(use-package company-rtags
  :ensure t
  :init
  (setq rtags-completions-enabled t)
  (push 'company-rtags company-backends))

(setq browse-url-browser-function #'w3m-browse-url)

(custom-set-variables
 ;; custom-set-variables was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(package-selected-packages
   '(web-mode php-mode markdown-mode langtool kconfig-mode w3m dockerfile-mode systemd cmake-mode yaml-mode powerline expand-region use-package org-roam magit lsp-ui lsp-treemacs helm-lsp helm-dash flycheck dts-mode company))
 '(reb-re-syntax 'rx))
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 )
