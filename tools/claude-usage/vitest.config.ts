import { defineConfig } from 'vitest/config';
import { vitestConfig } from '../vitest.base';

export default defineConfig(vitestConfig(import.meta.dirname));
