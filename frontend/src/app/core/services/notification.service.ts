import { Injectable, signal } from '@angular/core';

export interface Notification {
    id: string;
    userId: string;
    title: string;
    message: string;
    timestamp: Date;
    read: boolean;
    type: 'info' | 'success' | 'warning';
}

@Injectable({
    providedIn: 'root'
})
export class NotificationService {
    private notifications = signal<Notification[]>([
        {
            id: 'notif-001',
            userId: 'patron-001',
            title: 'Welcome to Pachyderm',
            message: 'Your account has been successfully created. Explore the catalog!',
            timestamp: new Date(Date.now() - 86400000 * 2), // 2 days ago
            read: true,
            type: 'info'
        },
        {
            id: 'notif-002',
            userId: 'patron-001',
            title: 'Hold Available',
            message: 'The Tragedy of Lorde Tuskar is now available for pickup at the main desk.',
            timestamp: new Date(Date.now() - 3600000), // 1 hour ago
            read: false,
            type: 'success'
        }
    ]);

    getNotifications(userId: string): Notification[] {
        return this.notifications().filter(n => n.userId === userId).sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
    }

    addNotification(notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) {
        const newNotif: Notification = {
            ...notification,
            id: `notif-${Date.now()}`,
            timestamp: new Date(),
            read: false
        };

        this.notifications.update(current => [newNotif, ...current]);
    }

    markAsRead(id: string) {
        this.notifications.update(current =>
            current.map(n => n.id === id ? { ...n, read: true } : n)
        );
    }

    markAllAsRead(userId: string) {
        this.notifications.update(current =>
            current.map(n => (n.userId === userId ? { ...n, read: true } : n))
        );
    }
}
