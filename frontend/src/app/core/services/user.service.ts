import { Injectable, computed, signal } from '@angular/core';

export interface UserIdentity {
    id: string;
    name: string;
    role: 'patron' | 'staff';
    avatarInitials: string;
}

export interface UserPermission {
    id: string;
    label: string;
    enabled: boolean;
}

const USER_STORAGE_KEY = 'ai_librarian_current_user';
const DEFAULT_USER: UserIdentity = {
    id: 'patron-001',
    name: 'Trunsworth Greyvale',
    role: 'patron',
    avatarInitials: 'TG'
};

const EVALUATION_PERSONAS: Readonly<Record<'patron' | 'staff', UserIdentity>> = {
    patron: {
        id: 'patron-001',
        name: 'Trunsworth Greyvale',
        role: 'patron',
        avatarInitials: 'TG',
    },
    staff: {
        id: 'patron-003',
        name: 'Marcus Tuskwell',
        role: 'staff',
        avatarInitials: 'MT',
    },
};

@Injectable({
    providedIn: 'root'
})
export class UserService {
    private currentUserSignal = signal<UserIdentity>(this.loadInitialUser());

    currentUser = this.currentUserSignal.asReadonly();

    isStaff = computed(() => this.currentUserSignal().role === 'staff');
    canViewAnalytics = computed(() => true);
    canRunBenchmarks = computed(() => true);
    canViewPatronDirectory = computed(() => this.isStaff());
    canSwitchAllPatrons = computed(() => true);

    readonly evaluationPersonas: readonly UserIdentity[] = [
        EVALUATION_PERSONAS.patron,
        EVALUATION_PERSONAS.staff,
    ];

    setCurrentUser(user: UserIdentity) {
        this.currentUserSignal.set(user);
        this.persistUser(user);
    }

    switchToEvaluationPersona(role: 'patron' | 'staff'): void {
        const target = EVALUATION_PERSONAS[role];
        this.setCurrentUser(target);
    }

    getEffectivePermissions(): UserPermission[] {
        return [
            { id: 'catalog_chat', label: 'Catalog + Chat', enabled: true },
            { id: 'analytics_view', label: 'Analytics View', enabled: this.canViewAnalytics() },
            { id: 'benchmark_control', label: 'Benchmark Controls', enabled: this.canRunBenchmarks() },
            { id: 'patron_directory', label: 'Patron Directory', enabled: this.canViewPatronDirectory() },
            { id: 'patron_switch', label: 'Cross-Patron Switch', enabled: this.canSwitchAllPatrons() },
        ];
    }

    private loadInitialUser(): UserIdentity {
        if (!this.hasLocalStorage()) return DEFAULT_USER;

        try {
            const raw = localStorage.getItem(USER_STORAGE_KEY);
            if (!raw) return DEFAULT_USER;
            const parsed = JSON.parse(raw) as UserIdentity;
            if (parsed?.id && parsed?.name && (parsed.role === 'patron' || parsed.role === 'staff')) {
                return parsed;
            }
            return DEFAULT_USER;
        } catch {
            return DEFAULT_USER;
        }
    }

    private persistUser(user: UserIdentity): void {
        if (!this.hasLocalStorage()) return;
        try {
            localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
        } catch {
            // Ignore localStorage write failures.
        }
    }

    private hasLocalStorage(): boolean {
        return typeof localStorage !== 'undefined';
    }
}
