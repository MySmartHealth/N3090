module.exports = {
  apps: [
    // FastAPI Gateway with JWT Authentication
    {
      name: 'api-gateway',
      cwd: '/home/dgs/N3090/services/inference-node',
      script: '.venv/bin/uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8000 --workers 4',
      interpreter: 'none',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      error_file: './logs/api-gateway-error.log',
      out_file: './logs/api-gateway-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      env: {
        PYTHONPATH: '/home/dgs/N3090/services/inference-node',
        ALLOW_INSECURE_DEV: 'false',
        JWT_SECRET: process.env.JWT_SECRET || 'CHANGE_ME_IN_PRODUCTION_ENV',
        JWT_ALGORITHM: 'HS256',
        JWT_EXPIRY_HOURS: '24',
        ADMIN_API_KEY: process.env.ADMIN_API_KEY || 'dev-admin-key-insecure',
        API_KEY_BIMEDIX2_8081: process.env.API_KEY_BIMEDIX2_8081,
        API_KEY_TINY_LLAMA_1B_8083: process.env.API_KEY_TINY_LLAMA_1B_8083,
        API_KEY_OPENINSURANCE_8084: process.env.API_KEY_OPENINSURANCE_8084,
        API_KEY_BIOMISTRAL_8085: process.env.API_KEY_BIOMISTRAL_8085,
      },
    },
    
    // Model Server: Tiny-LLaMA-1B (Port 8080, GPU 0) - Chat/Legacy
    {
      name: 'llama-tiny-8080',
      script: '/home/dgs/llama.cpp/build/bin/llama-server',
      args: [
        '-m', '/home/dgs/N3090/services/inference-node/models/tiny-llama-1.1b-chat-medical.fp16.gguf',
        '-c', '2048',
        '-ngl', '99',
        '--port', '8080',
        '--host', '0.0.0.0',
        '--api-key', process.env.API_KEY_TINY_LLAMA_1B_8080 || 'dev-key',
      ],
      env: { CUDA_VISIBLE_DEVICES: '0' },
      autorestart: true,
      max_memory_restart: '4G',
      error_file: './logs/llama-8080-error.log',
      out_file: './logs/llama-8080-out.log',
    },
    
    // Model Server: BiMediX2-8B (Port 8081, GPU 0) - MedicalQA
    {
      name: 'llama-bimedix2-8081',
      script: '/home/dgs/llama.cpp/build/bin/llama-server',
      args: [
        '-m', '/home/dgs/N3090/services/inference-node/models/BiMediX2-8B-hf.i1-Q6_K.gguf',
        '-c', '8192',
        '-ngl', '99',
        '--port', '8081',
        '--host', '0.0.0.0',
        '--api-key', process.env.API_KEY_BIMEDIX2_8081 || 'dev-key',
      ],
      env: { CUDA_VISIBLE_DEVICES: '0' },
      autorestart: true,
      max_memory_restart: '10G',
      error_file: './logs/llama-8081-error.log',
      out_file: './logs/llama-8081-out.log',
    },
    
    // Model Server: Tiny-LLaMA-1B (Port 8083, GPU 1) - Appointment/Monitoring
    {
      name: 'llama-tiny-8083',
      script: '/home/dgs/llama.cpp/build/bin/llama-server',
      args: [
        '-m', '/home/dgs/N3090/services/inference-node/models/tiny-llama-1.1b-chat-medical.fp16.gguf',
        '-c', '4096',
        '-ngl', '99',
        '--port', '8083',
        '--host', '0.0.0.0',
        '--api-key', process.env.API_KEY_TINY_LLAMA_1B_8083 || 'dev-key',
      ],
      env: { CUDA_VISIBLE_DEVICES: '1' },
      autorestart: true,
      max_memory_restart: '4G',
      error_file: './logs/llama-8083-error.log',
      out_file: './logs/llama-8083-out.log',
    },
    
    // Model Server: OpenInsurance-8B (Port 8084, GPU 1) - Billing/Claims
    {
      name: 'llama-openins-8084',
      script: '/home/dgs/llama.cpp/build/bin/llama-server',
      args: [
        '-m', '/home/dgs/N3090/services/inference-node/models/openinsurancellm-llama3-8b.Q5_K_M.gguf',
        '-c', '8192',
        '-ngl', '99',
        '--port', '8084',
        '--host', '0.0.0.0',
        '--api-key', process.env.API_KEY_OPENINSURANCE_8084 || 'dev-key',
      ],
      env: { CUDA_VISIBLE_DEVICES: '1' },
      autorestart: true,
      max_memory_restart: '10G',
      error_file: './logs/llama-8084-error.log',
      out_file: './logs/llama-8084-out.log',
    },
    
    // Model Server: BioMistral-7B (Port 8085, GPU 1) - Clinical
    {
      name: 'llama-biomistral-8085',
      script: '/home/dgs/llama.cpp/build/bin/llama-server',
      args: [
        '-m', '/home/dgs/N3090/services/inference-node/models/BioMistral-Clinical-7B.Q8_0.gguf',
        '-c', '4096',  // Reduced context to save memory
        '-ngl', '35',  // Fewer GPU layers to avoid OOM
        '--port', '8085',
        '--host', '0.0.0.0',
        '--api-key', process.env.API_KEY_BIOMISTRAL_8085 || 'dev-key',
      ],
      env: { CUDA_VISIBLE_DEVICES: '1' },  // Move to GPU 1
      autorestart: true,
      max_memory_restart: '12G',
      max_restarts: 3,  // Limit restarts
      min_uptime: '10s',  // Must stay up 10s to count as successful start
      error_file: './logs/llama-8085-error.log',
      out_file: './logs/llama-8085-out.log',
    },
  ],
};
