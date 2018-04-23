;; Look & feel
(setq inhibit-startup-screen t)
(set-default-font "DejaVu Sans Mono-9")
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

(global-set-key (kbd "C-x k") 'kill-this-buffer)
(setq confirm-kill-emacs 'y-or-n-p)

(setenv "SSH_AUTH_SOCK" (concat (getenv "HOME") "/.ssh-auth-sock"))

;; theme
(load-theme 'tango-dark t)

;; global hl
(global-hl-line-mode 1)
(set-face-background 'hl-line "gray12")
(set-face-foreground 'highlight nil)

(add-to-list 'load-path "~/.emacs.d/site-lisp/bb-mode")
(add-to-list 'load-path "~/.emacs.d/site-lisp/emacs-async")
(add-to-list 'load-path "~/.emacs.d/site-lisp/expand-region")
(add-to-list 'load-path "~/.emacs.d/site-lisp/helm")
(add-to-list 'load-path "~/.emacs.d/site-lisp/dash")
(add-to-list 'load-path "~/.emacs.d/site-lisp/magit/lisp")
(add-to-list 'load-path "~/.emacs.d/site-lisp/popup-el")
(add-to-list 'load-path "~/.emacs.d/site-lisp/with-editor")
(add-to-list 'load-path "~/.emacs.d/site-lisp/dts-mode")
(add-to-list 'load-path "~/.emacs.d/site-lisp/powerline")

;; expand-region
(require 'expand-region)
(global-set-key (kbd "C-=") 'er/expand-region)

;; dired listing using human readable sizes
(setq dired-listing-switches "-alh")

;; ;; cmake
;; (require 'cmake-mode)

;; bb-mode
(require 'bb-mode)
(setq auto-mode-alist (cons '("\\.bb$" . bb-mode) auto-mode-alist))
(setq auto-mode-alist (cons '("\\.inc$" . bb-mode) auto-mode-alist))
(setq auto-mode-alist (cons '("\\.bbappend$" . bb-mode) auto-mode-alist))
(setq auto-mode-alist (cons '("\\.bbclass$" . bb-mode) auto-mode-alist))

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

(global-set-key (kbd "C-.") 'other-window)
(global-auto-revert-mode t)

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

;; magit
(require 'magit)
(global-set-key (kbd "C-x g") 'magit-status)
(with-eval-after-load 'info
  (info-initialize)
  (add-to-list 'Info-directory-list
	       "~/.emacs.d/magit/Documentation/"))

;; helm
(require 'helm-config)
(require 'helm)
(global-set-key (kbd "C-c h") 'helm-command-prefix)
(global-set-key (kbd "M-x") 'helm-M-x)
(global-set-key (kbd "C-x b") 'helm-mini)
(global-set-key (kbd "C-c h g") 'helm-google-suggest)
(setq helm-M-x-fuzzy-match t)
(setq helm-buffers-fuzzy-matching t
      helm-recentf-fuzzy-match    t)
(global-set-key (kbd "C-x C-f") 'helm-find-files)
(global-unset-key (kbd "C-x c"))
(define-key helm-map (kbd "<tab>") 'helm-execute-persistent-action) ; rebind tab to run persistent action
(define-key helm-map (kbd "C-i") 'helm-execute-persistent-action) ; make TAB works in terminal
(define-key helm-map (kbd "C-z")  'helm-select-action) ; list actions using C-z
(when (executable-find "curl")
  (setq helm-google-suggest-use-curl-p t))

(setq helm-split-window-in-side-p           t ; open helm buffer inside current window, not occupy whole other window
      helm-move-to-line-cycle-in-source     t ; move to end or beginning of source when reaching top or bottom of source.
      helm-ff-search-library-in-sexp        t ; search for library in `require' and `declare-function' sexp.
      helm-scroll-amount                    8 ; scroll 8 lines other window using M-<next>/M-<prior>
      helm-ff-file-name-history-use-recentf t)
(helm-mode 1)

;; dts-mode
(require 'dts-mode)

;; powerline
(require 'powerline)
(powerline-default-theme)

;; ;; emacs backup configuration
(setq backup-directory-alist `(("." . "~/.saves")))
(setq backup-by-copying t)
(setq delete-old-versions t
  kept-new-versions 6
  kept-old-versions 2
  version-control t)

;; ;; org
;; (require 'org)
;; (global-set-key "\C-cl" 'org-store-link)
;; (global-set-key "\C-ca" 'org-agenda)
;; (global-set-key "\C-cb" 'org-iswitchb)
;; (global-set-key (kbd "C-c c") 'org-capture)
;; (setq org-agenda-files (quote ("~/org"
;;                                "~/org/projets")))
;; (setq org-directory "~/org")
;; (setq org-default-notes-file "~/org/refile.org")
;; (setq org-capture-templates
;;       (quote (("t" "todo" entry (file+headline "~/org/refile.org" "Tasks") "* TODO %?\n%U\n%a\n")
;;               ("n" "note" entry (file+headline "~/org/refile.org" "Notes") "* %? :NOTE:\n%U\n%a\n"))))
;; (setq org-refile-targets (quote ((nil :maxlevel . 1)
;;                                  (org-agenda-files :maxlevel . 1))))
;; (setq org-todo-keywords
;;       '((sequence "TODO" "WAITING" "ONGOING" "|" "DONE" "CANCELED")))
;; (setq org-todo-keyword-faces
;;       (quote (("TODO" :foreground "red" :weight bold)
;;               ("WAITING" :foreground "orange" :weight bold)
;;               ("ONGOING" :foreground "forest green" :weight bold)
;;               ("CANCELLED" :foreground "forest green" :weight bold))))

;; (org-babel-do-load-languages
;;  'org-babel-load-languages
;;  '((ditaa . t)))
;; (setq org-export-latex-listings t)
;; (setq org-latex-listings t)

;; ;; start emacs server process
;; (server-start)

;; (custom-set-variables
;;  ;; custom-set-variables was added by Custom.
;;  ;; If you edit it by hand, you could mess it up, so be careful.
;;  ;; Your init file should contain only one such instance.
;;  ;; If there is more than one, they won't work right.
;;  '(ansi-color-names-vector
;;    ["#3F3F3F" "#CC9393" "#7F9F7F" "#F0DFAF" "#8CD0D3" "#DC8CC3" "#93E0E3" "#DCDCCC"])
;;  '(custom-safe-themes
;;    (quote
;;     ("f3d6a49e3f4491373028eda655231ec371d79d6d2a628f08d5aa38739340540b" default)))
;;  '(fci-rule-color "#383838")
;;  '(nrepl-message-colors
;;    (quote
;;     ("#CC9393" "#DFAF8F" "#F0DFAF" "#7F9F7F" "#BFEBBF" "#93E0E3" "#94BFF3" "#DC8CC3")))
;;  '(vc-annotate-background "#2B2B2B")
;;  '(vc-annotate-color-map
;;    (quote
;;     ((20 . "#BC8383")
;;      (40 . "#CC9393")
;;      (60 . "#DFAF8F")
;;      (80 . "#D0BF8F")
;;      (100 . "#E0CF9F")
;;      (120 . "#F0DFAF")
;;      (140 . "#5F7F5F")
;;      (160 . "#7F9F7F")
;;      (180 . "#8FB28F")
;;      (200 . "#9FC59F")
;;      (220 . "#AFD8AF")
;;      (240 . "#BFEBBF")
;;      (260 . "#93E0E3")
;;      (280 . "#6CA0A3")
;;      (300 . "#7CB8BB")
;;      (320 . "#8CD0D3")
;;      (340 . "#94BFF3")
;;      (360 . "#DC8CC3"))))
;;  '(vc-annotate-very-old-color "#DC8CC3"))
;; (custom-set-faces
;;  ;; custom-set-faces was added by Custom.
;;  ;; If you edit it by hand, you could mess it up, so be careful.
;;  ;; Your init file should contain only one such instance.
;;  ;; If there is more than one, they won't work right.
;;  )
