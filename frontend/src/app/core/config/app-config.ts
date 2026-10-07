import { environment, ServiceEndpoints } from '../../../environments/environment';

type ServiceName = keyof ServiceEndpoints;

interface RuntimeAppConfig {
  serviceToken?: string;
  services?: Partial<ServiceEndpoints>;
}

declare global {
  interface Window {
    __AI_LIBRARY_CONFIG__?: RuntimeAppConfig;
  }
}

const runtimeConfig: RuntimeAppConfig =
  typeof window !== 'undefined' ? window.__AI_LIBRARY_CONFIG__ ?? {} : {};

const serviceConfig: ServiceEndpoints = {
  ...environment.services,
  ...(runtimeConfig.services ?? {}),
};

const serviceToken = runtimeConfig.serviceToken ?? environment.serviceToken;

export function getServiceUrl(serviceName: ServiceName): string {
  return serviceConfig[serviceName].replace(/\/$/, '');
}

export function getServiceHeaders(): Record<string, string> {
  return serviceToken ? { 'X-Service-Token': serviceToken } : {};
}
