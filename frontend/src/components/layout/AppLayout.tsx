import { Suspense } from 'react';
import { NavLink as RouterNavLink, Link as RouterLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Avatar,
  Box,
  Flex,
  HStack,
  IconButton,
  Menu,
  MenuButton,
  MenuDivider,
  MenuGroup,
  MenuItem,
  MenuList,
  Text,
} from '@chakra-ui/react';
import { useAuth } from '../../context/AuthContext';
import { LoadingScreen } from '../ui/LoadingScreen';
import { MotionBox } from '../ui/motion';

interface NavItem {
  label: string;
  to: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'Projects', to: '/projects' },
  { label: 'Admin', to: '/admin', adminOnly: true },
];

function NavItemLink({ item }: { item: NavItem }) {
  return (
    <MotionBox whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }}>
      <Box
        as={RouterNavLink}
        to={item.to}
        px={3}
        py={2}
        borderRadius="full"
        fontWeight="medium"
        color="gray.600"
        _hover={{ bg: 'brand.50', color: 'brand.700' }}
        sx={{ '&.active': { bg: 'brand.100', color: 'brand.700' } }}
      >
        {item.label}
      </Box>
    </MotionBox>
  );
}

/** Authenticated shell: top nav + routed page content via <Outlet />. */
export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || user?.is_admin === true);
  const displayName = user?.full_name ?? user?.email ?? '';

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <Flex direction="column" minH="100vh">
      <Box
        as="header"
        position="sticky"
        top={0}
        zIndex="sticky"
        bg="whiteAlpha.800"
        backdropFilter="blur(12px)"
        borderBottomWidth="1px"
        borderColor="gray.100"
      >
        <Flex maxW="6xl" mx="auto" px={{ base: 4, md: 8 }} h={16} align="center" justify="space-between" gap={4}>
          <HStack spacing={8}>
            <Text
              as={RouterLink}
              to="/dashboard"
              fontWeight="extrabold"
              fontSize="lg"
              bgGradient="linear(to-r, brand.600, accent.500)"
              bgClip="text"
              whiteSpace="nowrap"
            >
              Project Verification
            </Text>
            <HStack as="nav" spacing={1} display={{ base: 'none', md: 'flex' }} aria-label="Main navigation">
              {items.map((item) => (
                <NavItemLink key={item.to} item={item} />
              ))}
            </HStack>
          </HStack>

          <HStack spacing={2}>
            <Menu>
              <MenuButton
                as={IconButton}
                aria-label="Open navigation"
                display={{ base: 'inline-flex', md: 'none' }}
                variant="ghost"
                icon={<Text fontSize="xl">☰</Text>}
              />
              <MenuList>
                {items.map((item) => (
                  <MenuItem key={item.to} as={RouterLink} to={item.to}>
                    {item.label}
                  </MenuItem>
                ))}
              </MenuList>
            </Menu>
            <Menu placement="bottom-end">
              <MenuButton aria-label="User menu" borderRadius="full">
                <Avatar size="sm" name={displayName} src={user?.avatar_url ?? undefined} bg="brand.500" color="white" />
              </MenuButton>
              <MenuList>
                <MenuGroup title={displayName}>
                  <MenuItem as={RouterLink} to="/profile">
                    Profile
                  </MenuItem>
                  <MenuItem as={RouterLink} to="/settings">
                    Settings
                  </MenuItem>
                </MenuGroup>
                <MenuDivider />
                <MenuItem color="red.500" onClick={() => void handleLogout()}>
                  Logout
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </Flex>
      </Box>
      <Box as="main" flex="1">
        <Suspense fallback={<LoadingScreen fullScreen={false} />}>
          <Outlet />
        </Suspense>
      </Box>
    </Flex>
  );
}
