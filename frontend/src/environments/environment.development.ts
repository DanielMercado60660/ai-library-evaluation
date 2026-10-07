export interface ServiceEndpoints {
  agents: string;
  catalog: string;
  circulation: string;
  ill: string;
  registry: string;
}

export interface AppEnvironment {
  production: boolean;
  serviceToken: string;
  services: ServiceEndpoints;
}

export const environment: AppEnvironment = {
  production: false,
  serviceToken: 'dev-token-ai-librarian',
  services: {
    agents: 'http://localhost:8000',
    catalog: 'http://localhost:8001',
    circulation: 'http://localhost:8002',
    ill: 'http://localhost:8003',
    registry: 'http://localhost:8004',
  },
};
